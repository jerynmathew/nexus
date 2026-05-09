from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from typing import Any

from nexus.transport.base import Button, InboundMessage

logger = logging.getLogger(__name__)


class CLITransport:
    def __init__(
        self,
        conversation_manager_send: Callable[..., Any],
        tenant_id: str = "cli_user",
    ) -> None:
        self._send_to_conv_manager = conversation_manager_send
        self._tenant_id = tenant_id
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def transport_name(self) -> str:
        return "cli"

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _read_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except EOFError:
                break
            if not line:
                break

            text = line.strip()
            if not text:
                continue

            if text.lower() in ("quit", "exit", "/quit", "/exit"):
                self._running = False
                break

            inbound = InboundMessage(
                tenant_id=self._tenant_id,
                text=text,
                channel_id="cli",
                reply_transport=self,
            )
            await self._send_to_conv_manager(
                {
                    "action": "inbound_message",
                    **inbound.to_payload(),
                }
            )

    async def send_text(self, channel_id: str, text: str) -> None:
        print(f"\n{text}\n")

    async def send_buttons(
        self,
        channel_id: str,
        text: str,
        buttons: list[Button],
    ) -> None:
        print(f"\n{text}")
        for i, btn in enumerate(buttons, 1):
            print(f"  [{i}] {btn.label}")
        print()

    async def send_typing(self, channel_id: str) -> None:
        pass
