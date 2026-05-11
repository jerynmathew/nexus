from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from nexus.transport.base import Button, InboundMessage

logger = logging.getLogger(__name__)


class DiscordTransport:
    def __init__(
        self,
        bot_token: str,
        conversation_manager_send: Callable[..., Any],
        tenant_resolver: Callable[[str], str | None],
        command_prefix: str = "!",
    ) -> None:
        self._bot_token = bot_token
        self._send_to_conv_manager = conversation_manager_send
        self._resolve = tenant_resolver
        self._command_prefix = command_prefix
        self._client: Any = None

    @property
    def transport_name(self) -> str:
        return "discord"

    async def start(self) -> None:
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError(
                "discord.py is required for Discord transport. "
                "Install with: pip install 'nexus[discord]'"
            ) from exc

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        transport = self

        @self._client.event
        async def on_ready() -> None:
            logger.info("Discord transport connected as %s", self._client.user)

        @self._client.event
        async def on_message(message: Any) -> None:
            if message.author == self._client.user:
                return
            if message.author.bot:
                return

            is_dm = not hasattr(message.channel, "guild") or message.channel.guild is None
            is_mention = self._client.user in message.mentions if self._client.user else False

            if not is_dm and not is_mention:
                return

            user_id = str(message.author.id)
            tenant_id = transport._resolve(user_id)
            if tenant_id is None:
                await message.channel.send("Sorry, you're not authorized.")
                return

            text = message.content
            if is_mention and self._client.user:
                text = text.replace(f"<@{self._client.user.id}>", "").strip()

            if text.startswith(transport._command_prefix):
                parts = text[len(transport._command_prefix) :].split(maxsplit=1)
                cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                await transport._send_to_conv_manager(
                    {
                        "action": "command",
                        "tenant_id": tenant_id,
                        "channel_id": str(message.channel.id),
                        "command": cmd,
                        "args": args,
                    }
                )
                return

            inbound = InboundMessage(
                tenant_id=tenant_id,
                text=text,
                channel_id=str(message.channel.id),
                reply_transport=transport,
                message_id=str(message.id),
            )
            await transport._send_to_conv_manager(
                {
                    "action": "inbound_message",
                    **inbound.to_payload(),
                }
            )

        import asyncio

        self._task = asyncio.create_task(self._client.start(self._bot_token))

    async def stop(self) -> None:
        if self._client:
            await self._client.close()

    async def send_text(self, channel_id: str, text: str) -> None:
        if not self._client:
            return
        channel = self._client.get_channel(int(channel_id))
        if channel:
            for chunk in _split_discord(text):
                await channel.send(chunk)

    async def send_buttons(
        self,
        channel_id: str,
        text: str,
        buttons: list[Button],
    ) -> None:
        if not self._client:
            return
        channel = self._client.get_channel(int(channel_id))
        if channel:
            button_text = "\n".join(f"  [{b.label}]" for b in buttons)
            await channel.send(f"{text}\n{button_text}")

    async def send_typing(self, channel_id: str) -> None:
        if not self._client:
            return
        channel = self._client.get_channel(int(channel_id))
        if channel:
            await channel.typing()


def _split_discord(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
