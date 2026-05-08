# Design: Transport Abstraction

> Multi-transport architecture — how Nexus decouples messaging platforms from the conversation engine.

**Status:** Draft
**Module:** `src/nexus/transport/`
**First implementation:** Telegram (M1.2)

---

## Problem

Coupling to a single messaging platform (Vigil was Telegram-only until M5.x) creates vendor lock-in and makes the codebase fragile — Telegram-specific objects leak into agent logic, making it impossible to add Discord or CLI without rewriting the conversation manager.

---

## Design

### BaseTransport Protocol

```python
from typing import Protocol

class BaseTransport(Protocol):
    """Protocol for messaging platform transports."""

    @property
    def transport_name(self) -> str:
        """Identifier: 'telegram', 'discord', 'cli', etc."""
        ...

    async def start(self) -> None:
        """Start listening for messages. Non-blocking."""
        ...

    async def stop(self) -> None:
        """Graceful shutdown."""
        ...

    # --- Outbound: text ---
    async def send_text(self, channel_id: str, text: str) -> None:
        """Send a text message to a channel/chat."""
        ...

    async def send_buttons(
        self, channel_id: str, text: str, buttons: list[Button],
    ) -> None:
        """Send a message with inline action buttons (approve/reject/etc)."""
        ...

    # --- Outbound: media ---
    async def send_photo(self, channel_id: str, photo: bytes, caption: str = "") -> None:
        """Send a photo with optional caption."""
        ...

    async def send_voice(self, channel_id: str, audio: bytes) -> None:
        """Send a voice message (OGG/Opus)."""
        ...

    async def send_document(self, channel_id: str, document: bytes, filename: str,
                             caption: str = "") -> None:
        """Send a file attachment."""
        ...

    # --- Tenant ---
    def resolve_tenant(self, transport_user_id: str) -> str | None:
        """Map transport-specific user ID to Nexus tenant_id."""
        ...
```

### InboundMessage

Every transport converts its native event into this normalized dataclass:

```python
@dataclass(frozen=True)
class InboundMessage:
    """Transport-agnostic inbound message."""
    tenant_id: str                      # resolved by transport
    text: str                           # message content (or transcription for voice)
    channel_id: str                     # transport-specific chat/channel ID
    reply_transport: BaseTransport      # reference for replying
    message_id: str | None = None       # transport-specific message ID
    media_type: str | None = None       # "photo" | "voice" | "video" | "document" | None
    media_bytes: bytes | None = None    # raw media content (downloaded by transport)
    media_caption: str | None = None    # caption on photo/video (if any)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict:
        """Serialize for Civitas Message.payload."""
        ...

    @classmethod
    def from_payload(cls, payload: dict) -> InboundMessage:
        """Deserialize from Civitas Message.payload."""
        ...
```

### Button

For approval flows (governance gates):

```python
@dataclass(frozen=True)
class Button:
    label: str              # "Approve", "Reject", "View"
    callback_data: str      # "approve:skill:email-triage:v3"
```

---

## TelegramTransport

First and primary transport implementation.

```python
class TelegramTransport:
    """Telegram Bot API transport — polling mode."""

    def __init__(
        self,
        bot_token: str,
        conversation_manager_name: str,
        tenant_resolver: Callable[[str], str | None],
    ) -> None:
        self._bot = telegram.Bot(token=bot_token)
        self._app = ApplicationBuilder().token(bot_token).build()
        self._conv_manager = conversation_manager_name
        self._resolve = tenant_resolver

    @property
    def transport_name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        self._app.add_handler(MessageHandler(filters.TEXT, self._on_text))
        self._app.add_handler(MessageHandler(filters.VOICE, self._on_voice))
        self._app.add_handler(CallbackQueryHandler(self._on_callback))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        inbound = InboundMessage(
            tenant_id=tenant_id,
            text=update.message.text,
            channel_id=str(update.effective_chat.id),
            reply_transport=self,
            message_id=str(update.message.message_id),
        )
        # Send to ConversationManager via Civitas MessageBus
        await self._bus.send(self._conv_manager, {
            "action": "inbound_message",
            **inbound.to_payload(),
        })

    async def send_text(self, channel_id: str, text: str) -> None:
        await self._bot.send_message(chat_id=int(channel_id), text=text)

    async def send_buttons(self, channel_id: str, text: str, buttons: list[Button]) -> None:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(b.label, callback_data=b.callback_data) for b in buttons]
        ])
        await self._bot.send_message(
            chat_id=int(channel_id), text=text, reply_markup=keyboard,
        )
```

**Key decisions:**
- **Polling mode** for M1 (no public URL needed for homelab). Webhook mode as future option.
- **Typing indicators** sent during processing (`await bot.send_chat_action(chat_id, "typing")`)
- **Transport never calls LLM or MCP** — it converts native events to `InboundMessage` and sends to ConversationManager via the message bus.

---

## Media Handling

Transports handle inbound media download and outbound media delivery. Processing (vision, STT, TTS) happens in ConversationManager, not in the transport.

### Inbound Media (user → Nexus)

| Media type | Transport responsibility | ConversationManager responsibility |
|---|---|---|
| **Photo** | Download image bytes, set `media_type="photo"` | Send to vision-capable LLM (Claude, GPT-4o) for description/analysis |
| **Voice** | Download OGG/Opus bytes, set `media_type="voice"` | STT transcription (Whisper API or local faster-whisper) → process as text |
| **Video** | Download video, extract audio (ffmpeg), set `media_type="video"` | Audio → STT → text. Optionally: extract frames → vision LLM |
| **Document** | Download file bytes, set `media_type="document"` | Parse content (PDF/text) → include in LLM context |

### TelegramTransport Media Handlers

```python
async def _on_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = update.message.photo[-1]  # highest resolution
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()

    inbound = InboundMessage(
        tenant_id=self._resolve(str(update.effective_user.id)),
        text=update.message.caption or "",
        channel_id=str(update.effective_chat.id),
        reply_transport=self,
        media_type="photo",
        media_bytes=bytes(photo_bytes),
        media_caption=update.message.caption,
    )
    await self._send_to_conv_manager(inbound)

async def _on_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file = await update.message.voice.get_file()
    voice_bytes = await file.download_as_bytearray()

    inbound = InboundMessage(
        tenant_id=self._resolve(str(update.effective_user.id)),
        text="",  # will be populated by STT in ConversationManager
        channel_id=str(update.effective_chat.id),
        reply_transport=self,
        media_type="voice",
        media_bytes=bytes(voice_bytes),
    )
    await self._send_to_conv_manager(inbound)

async def _on_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    video = update.message.video or update.message.video_note
    file = await video.get_file()
    video_bytes = await file.download_as_bytearray()

    # Extract audio via ffmpeg (pipe, no temp files)
    audio_bytes = await self._extract_audio(video_bytes)

    inbound = InboundMessage(
        tenant_id=self._resolve(str(update.effective_user.id)),
        text="",
        channel_id=str(update.effective_chat.id),
        reply_transport=self,
        media_type="video",
        media_bytes=audio_bytes,  # audio extracted, video discarded
        media_caption=update.message.caption,
    )
    await self._send_to_conv_manager(inbound)
```

### Outbound Media (Nexus → user)

ConversationManager calls `reply_transport.send_photo()`, `send_voice()`, `send_document()` with raw bytes. Transport handles platform-specific formatting.

**TTS response flow:**
```
LLM generates text response
  → ModelRouter: TTS model configured?
    → YES: generate audio (OpenAI TTS / Kokoro / Piper)
    → send_voice(audio_bytes)
    → AND send_text(text) as caption
  → NO: send_text(text) only
```

**Chart/image response flow:**
```
LLM output contains chart data (Chart.js config)
  → QuickChart.io API → PNG bytes (or fallback to text table)
  → send_photo(png_bytes, caption="Gold price this week")
```

---

## Tenant Resolution

Each transport resolves its native user ID to a Nexus `tenant_id`:

```python
class TenantResolver:
    """Shared tenant resolution logic — queries MemoryAgent for transport ID mapping."""

    async def resolve(self, transport: str, transport_user_id: str) -> str | None:
        result = await self._memory.ask({
            "action": "config_get",
            "namespace": "transport_ids",
            "key": transport,
            "value": transport_user_id,
        })
        return result.payload.get("tenant_id")
```

**Mapping storage** in `user_config` table:

```
(tenant_id, "transport_ids", "telegram", "123456789")
(tenant_id, "transport_ids", "discord",  "98765")
```

**Cross-transport continuity:** Same tenant_id resolved from Telegram and Discord → same memory, same persona, same conversation history.

---

## Adding a New Transport

1. Implement `BaseTransport` protocol
2. Handle native events → convert to `InboundMessage`
3. Send to ConversationManager via `bus.send(conv_manager, inbound.to_payload())`
4. Implement `send_text()`, `send_buttons()`, etc. for outbound
5. Register in `topology.yaml`:
   ```yaml
   transports:
     - type: nexus.transport.discord.DiscordTransport
       config:
         bot_token: "${DISCORD_BOT_TOKEN}"
   ```
6. Add transport ID mapping for tenants in `user_config`

**No changes to ConversationManager required.** It only sees `InboundMessage` and calls `reply_transport.send_text()`.

---

## Future Transports

| Transport | Priority | Notes |
|---|---|---|
| Discord | M4.1 | `discord.py` library, similar handler pattern to Telegram |
| Slack | M4.1 | Via Slack MCP (read) + Bolt SDK (write/interactive) |
| CLI | Future | stdin/stdout transport for development and testing |
| SMS | Future | Twilio API |
| Web | Future | WebSocket transport for browser dashboard chat |
