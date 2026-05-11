from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from nexus.transport.base import Button, InboundMessage

logger = logging.getLogger(__name__)


class SlackTransport:
    def __init__(
        self,
        bot_token: str,
        signing_secret: str,
        conversation_manager_send: Callable[..., Any],
        tenant_resolver: Callable[[str], str | None],
        port: int = 3002,
    ) -> None:
        self._bot_token = bot_token
        self._signing_secret = signing_secret
        self._send_to_conv_manager = conversation_manager_send
        self._resolve = tenant_resolver
        self._port = port
        self._app: Any = None
        self._handler: Any = None

    @property
    def transport_name(self) -> str:
        return "slack"

    async def start(self) -> None:
        try:
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
            from slack_bolt.async_app import AsyncApp
        except ImportError as exc:
            raise RuntimeError(
                "slack-bolt is required for Slack transport. "
                "Install with: pip install 'nexus[slack]'"
            ) from exc

        self._app = AsyncApp(
            token=self._bot_token,
            signing_secret=self._signing_secret,
        )
        transport = self

        @self._app.event("message")
        async def handle_message(event: dict[str, Any], say: Any) -> None:
            if event.get("subtype"):
                return

            user_id = event.get("user", "")
            tenant_id = transport._resolve(user_id)
            if tenant_id is None:
                await say("Sorry, you're not authorized.")
                return

            text = event.get("text", "")
            channel_id = event.get("channel", "")

            inbound = InboundMessage(
                tenant_id=tenant_id,
                text=text,
                channel_id=channel_id,
                reply_transport=transport,
                message_id=event.get("ts", ""),
            )
            await transport._send_to_conv_manager(
                {
                    "action": "inbound_message",
                    **inbound.to_payload(),
                }
            )

        @self._app.event("app_mention")
        async def handle_mention(event: dict[str, Any], say: Any) -> None:
            await handle_message(event, say)

        self._handler = AsyncSocketModeHandler(self._app, self._bot_token)
        await self._handler.start_async()
        logger.info("Slack transport started")

    async def stop(self) -> None:
        if self._handler:
            await self._handler.close_async()

    async def send_text(self, channel_id: str, text: str) -> None:
        if not self._app:
            return
        await self._app.client.chat_postMessage(channel=channel_id, text=text)

    async def send_buttons(
        self,
        channel_id: str,
        text: str,
        buttons: list[Button],
    ) -> None:
        if not self._app:
            return
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": b.label},
                        "action_id": b.callback_data,
                    }
                    for b in buttons
                ],
            },
        ]
        await self._app.client.chat_postMessage(
            channel=channel_id,
            text=text,
            blocks=blocks,
        )

    async def send_typing(self, channel_id: str) -> None:
        pass
