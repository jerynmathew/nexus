# M3 Wave B Implementation Plan — Media Support: "It hears you, it sees you"

> Version: 1.0
> Created: 2026-05-09
> Status: Review
> Depends on: M3 Wave A complete

---

## Scope

Wave B adds inbound media support: voice messages, photos, and documents. Outbound voice (TTS) is designed as a pluggable interface but deferred until GPU hardware is confirmed.

| Component | What ships | Backend |
|---|---|---|
| **STT** | Voice messages → text → conversation | faster-whisper (local, CPU) |
| **Vision** | Photo analysis → text description | Claude (via AgentGateway, already available) |
| **Documents** | PDF/text parsing → LLM context | Built-in (PyPDF2 / plain text) |
| **TTS interface** | Protocol defined, backend pluggable | Not implemented (Qwen3-TTS/CosyVoice/Chatterbox when ready) |

## Key Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | faster-whisper for STT | Local, free, CPU-capable. ~240MB model. No cloud dependency. |
| 2 | Claude for vision | Already available via AgentGateway. Claude has native vision. No extra model. |
| 3 | TTS interface only, no implementation | All good voice cloning options need GPU. Design the protocol, plug in later. |
| 4 | Transport handles download, ConvManager handles processing | Transport downloads bytes, converts to InboundMessage. ConvManager runs STT/vision. |

---

## Task Breakdown

### Phase 1: Media Handler Interface

#### T3.4.1 — MediaHandler protocol (`src/nexus/media/handler.py`)
- [ ] `STTProvider` Protocol: `async transcribe(audio_bytes: bytes, format: str) -> str`
- [ ] `TTSProvider` Protocol: `async synthesize(text: str, voice_ref: bytes | None) -> bytes`
- [ ] `VisionProvider` Protocol: `async describe(image_bytes: bytes, prompt: str) -> str`
- [ ] `MediaHandler` class: wires STT/TTS/Vision providers
  - `async process_voice(audio_bytes: bytes) -> str` — STT → text
  - `async process_image(image_bytes: bytes, caption: str) -> str` — Vision → description
  - `async process_document(doc_bytes: bytes, filename: str) -> str` — Parse → text
  - `async generate_voice(text: str) -> bytes | None` — TTS (returns None if no provider)
- **Tests:**
  - [ ] Protocol compliance checks
  - [ ] MediaHandler with mock providers

### Phase 2: STT via faster-whisper

#### T3.4.2 — WhisperSTT provider (`src/nexus/media/stt.py`)
- [ ] `WhisperSTT` implementing `STTProvider`
- [ ] Uses `faster-whisper` library with `small` model (244MB, good balance of speed/accuracy)
- [ ] Model downloaded on first use, cached
- [ ] Accepts OGG/Opus (Telegram voice format), WAV, MP3
- [ ] Returns transcribed text
- [ ] Runs on CPU — no CUDA required
- [ ] Add `faster-whisper` to optional deps: `nexus[voice]`
- **Tests:**
  - [ ] Mock audio → transcription (mock the model, test the pipeline)

#### T3.4.3 — ClaudeVision provider (`src/nexus/media/vision.py`)
- [ ] `ClaudeVision` implementing `VisionProvider`
- [ ] Sends image as base64 to LLMClient with vision prompt
- [ ] AgentGateway passes image content to Claude (which has native vision)
- [ ] Returns text description/analysis
- **Tests:**
  - [ ] Mock LLM response for image description

#### T3.4.4 — Document parser (`src/nexus/media/documents.py`)
- [ ] Plain text: read directly
- [ ] PDF: extract text (PyPDF2 or pdfplumber)
- [ ] Add PDF library to optional deps: `nexus[docs]`
- [ ] Truncate to max context size
- **Tests:**
  - [ ] Plain text extraction
  - [ ] PDF text extraction (mock or tiny test PDF)

### Phase 3: Transport Media Handlers

#### T3.4.5 — Telegram voice handler
- [ ] `_on_voice` handler in TelegramTransport
- [ ] Download OGG/Opus bytes from Telegram
- [ ] Build InboundMessage with `media_type="voice"`, `media_bytes=audio_data`
- [ ] Send to ConversationManager
- **Tests:**
  - [ ] Mock voice message → InboundMessage with correct media fields

#### T3.4.6 — Telegram photo handler
- [ ] `_on_photo` handler in TelegramTransport
- [ ] Download highest-resolution photo
- [ ] Build InboundMessage with `media_type="photo"`, `media_bytes=image_data`
- [ ] Include caption if present
- **Tests:**
  - [ ] Mock photo message → InboundMessage with image bytes

#### T3.4.7 — Telegram document handler
- [ ] `_on_document` handler in TelegramTransport
- [ ] Download document bytes
- [ ] Build InboundMessage with `media_type="document"`, `media_bytes=doc_bytes`
- [ ] Include filename in metadata
- **Tests:**
  - [ ] Mock document message → InboundMessage with doc bytes

### Phase 4: ConversationManager Media Processing

#### T3.4.8 — Wire MediaHandler into ConversationManager
- [ ] On `media_type="voice"`: run STT → use transcribed text as message content
- [ ] On `media_type="photo"`: run Vision → include description in context
- [ ] On `media_type="document"`: parse → include extracted text in context
- [ ] Show typing indicator during processing
- [ ] Log media processing to activity feed
- **Tests:**
  - [ ] Voice message → STT → LLM response
  - [ ] Photo → vision description → LLM response
  - [ ] Document → parsed text → LLM response

---

## TTS Interface (designed, not implemented)

The `TTSProvider` protocol is defined for future implementation:

```python
class TTSProvider(Protocol):
    async def synthesize(self, text: str, voice_ref: bytes | None = None) -> bytes: ...
```

When a GPU-capable backend is chosen (Qwen3-TTS, CosyVoice, etc.), implement this protocol and wire it into MediaHandler. The ConversationManager will call `media_handler.generate_voice(response_text)` and send the result via `transport.send_voice()`.

Candidate backends (all Apache 2.0, all need GPU):
- **Qwen3-TTS**: 3s voice clone, 10 languages, streaming, emotion control
- **CosyVoice 3.0**: Best cross-lingual, 9 languages
- **OmniVoice**: 600+ languages, fastest inference (RTF 0.025)
- **Chatterbox Turbo**: MIT, smallest (350M), English focused

---

## Dependencies

```toml
[project.optional-dependencies]
voice = [
    "faster-whisper>=1.0",
]
docs = [
    "pdfplumber>=0.11",
]
```

No new core dependencies. Voice and document support are optional extras.

---

## Progress Tracking

| Phase | Task | Status | Notes |
|---|---|---|---|
| 1 | T3.4.1 MediaHandler protocol | ⬜ Not started | |
| 2 | T3.4.2 WhisperSTT provider | ⬜ Not started | |
| 2 | T3.4.3 ClaudeVision provider | ⬜ Not started | |
| 2 | T3.4.4 Document parser | ⬜ Not started | |
| 3 | T3.4.5 Telegram voice handler | ⬜ Not started | |
| 3 | T3.4.6 Telegram photo handler | ⬜ Not started | |
| 3 | T3.4.7 Telegram document handler | ⬜ Not started | |
| 4 | T3.4.8 Wire into ConversationManager | ⬜ Not started | |
