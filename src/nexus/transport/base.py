from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class Button:
    label: str
    callback_data: str


@runtime_checkable
class BaseTransport(Protocol):
    @property
    def transport_name(self) -> str: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def send_text(self, channel_id: str, text: str) -> None: ...

    async def send_buttons(
        self,
        channel_id: str,
        text: str,
        buttons: list[Button],
    ) -> None: ...

    async def send_typing(self, channel_id: str) -> None: ...


@dataclass(frozen=True)
class InboundMessage:
    tenant_id: str
    text: str
    channel_id: str
    reply_transport: BaseTransport
    message_id: str | None = None
    media_type: str | None = None
    media_bytes: bytes | None = None
    media_caption: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "text": self.text,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "media_type": self.media_type,
            "media_caption": self.media_caption,
            "metadata": self.metadata,
        }

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        reply_transport: BaseTransport,
        media_bytes: bytes | None = None,
    ) -> InboundMessage:
        return cls(
            tenant_id=payload.get("tenant_id", ""),
            text=payload.get("text", ""),
            channel_id=payload.get("channel_id", ""),
            reply_transport=reply_transport,
            message_id=payload.get("message_id"),
            media_type=payload.get("media_type"),
            media_bytes=media_bytes,
            media_caption=payload.get("media_caption"),
            metadata=payload.get("metadata", {}),
        )
