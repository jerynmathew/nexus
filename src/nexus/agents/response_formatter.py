from __future__ import annotations

import contextlib
import logging
from typing import Any

from nexus.config import DashboardConfig
from nexus.dashboard.views import ContentStore

logger = logging.getLogger(__name__)

_LONG_RESPONSE_THRESHOLD = 2000


class ResponseFormatter:
    def __init__(
        self,
        default_transport: Any = None,
        content_store: ContentStore | None = None,
        dashboard_config: DashboardConfig | None = None,
    ) -> None:
        self._default_transport = default_transport
        self._transports: dict[str, Any] = {}
        self._content_store = content_store
        self._dashboard_config = dashboard_config

    def set_default_transport(self, transport: Any) -> None:
        self._default_transport = transport

    def add_transport(self, prefix: str, transport: Any) -> None:
        self._transports[prefix] = transport

    def set_content_store(self, store: ContentStore, config: DashboardConfig) -> None:
        self._content_store = store
        self._dashboard_config = config

    def _resolve_transport(self, channel_id: str) -> Any:
        for prefix, transport in self._transports.items():
            if channel_id.startswith(prefix):
                return transport
        return self._default_transport

    async def send_reply(self, channel_id: str, text: str) -> None:
        transport = self._resolve_transport(channel_id)
        if transport and hasattr(transport, "send_text"):
            try:
                await transport.send_text(channel_id, text)
            except Exception:
                logger.debug("Failed to send reply via transport")

    async def send_response(self, channel_id: str, response_text: str) -> None:
        if (
            len(response_text) > _LONG_RESPONSE_THRESHOLD
            and self._content_store
            and self._dashboard_config
        ):
            view_id = self._content_store.store(response_text)
            if self._dashboard_config.base_url:
                base = self._dashboard_config.base_url.rstrip("/")
            else:
                base = f"http://{self._dashboard_config.host}:{self._dashboard_config.port}"
            view_url = f"{base}/view/{view_id}"
            tldr = response_text[:300].rsplit(" ", 1)[0] + "..."
            await self.send_reply(
                channel_id,
                f"{tldr}\n\nSee full details → {view_url}",
            )
        else:
            await self.send_reply(channel_id, response_text)

    async def send_typing(self, channel_id: str) -> None:
        transport = self._resolve_transport(channel_id)
        if transport and hasattr(transport, "send_typing"):
            with contextlib.suppress(Exception):
                await transport.send_typing(channel_id)
