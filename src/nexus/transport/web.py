from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from nexus.transport.base import Button

logger = logging.getLogger(__name__)


class WebTransport:
    def __init__(
        self,
        conversation_manager_send: Callable[..., Any],
        tenant_id: str = "",
    ) -> None:
        self._send_to_conv_manager = conversation_manager_send
        self._default_tenant = tenant_id
        self._connections: dict[str, asyncio.Queue[str]] = {}

    @property
    def transport_name(self) -> str:
        return "web"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self._connections.clear()

    def register_connection(self, channel_id: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._connections[channel_id] = queue
        return queue

    def unregister_connection(self, channel_id: str) -> None:
        self._connections.pop(channel_id, None)

    async def handle_message(self, channel_id: str, text: str, tenant_id: str = "") -> None:
        tid = tenant_id or self._default_tenant
        if not tid:
            await self._send_to_queue(channel_id, "Not authenticated.")
            return

        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lstrip("/")
            args = parts[1] if len(parts) > 1 else ""
            await self._send_to_conv_manager(
                {
                    "action": "command",
                    "tenant_id": tid,
                    "channel_id": f"web_{channel_id}",
                    "command": cmd,
                    "args": args,
                }
            )
        else:
            await self._send_to_conv_manager(
                {
                    "action": "inbound_message",
                    "tenant_id": tid,
                    "text": text,
                    "channel_id": f"web_{channel_id}",
                }
            )

    async def send_text(self, channel_id: str, text: str) -> None:
        clean_id = channel_id.removeprefix("web_")
        await self._send_to_queue(clean_id, text)

    async def send_buttons(
        self,
        channel_id: str,
        text: str,
        buttons: list[Button],
    ) -> None:
        clean_id = channel_id.removeprefix("web_")
        button_text = "\n".join(f"[{b.label}]" for b in buttons)
        await self._send_to_queue(clean_id, f"{text}\n{button_text}")

    async def send_typing(self, channel_id: str) -> None:
        clean_id = channel_id.removeprefix("web_")
        queue = self._connections.get(clean_id)
        if queue:
            await queue.put(json.dumps({"type": "typing"}))

    async def _send_to_queue(self, channel_id: str, text: str) -> None:
        queue = self._connections.get(channel_id)
        if queue:
            await queue.put(json.dumps({"type": "message", "text": text}))
