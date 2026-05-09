from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from nexus.transport.base import Button, InboundMessage


class TestInboundMessage:
    def test_to_payload_roundtrip(self) -> None:
        transport = AsyncMock()
        transport.transport_name = "test"

        msg = InboundMessage(
            tenant_id="t1",
            text="hello",
            channel_id="ch1",
            reply_transport=transport,
            message_id="m1",
            metadata={"key": "value"},
        )

        payload = msg.to_payload()
        assert payload["tenant_id"] == "t1"
        assert payload["text"] == "hello"
        assert payload["channel_id"] == "ch1"
        assert payload["message_id"] == "m1"
        assert payload["metadata"] == {"key": "value"}

        restored = InboundMessage.from_payload(payload, reply_transport=transport)
        assert restored.tenant_id == "t1"
        assert restored.text == "hello"
        assert restored.channel_id == "ch1"

    def test_media_fields(self) -> None:
        transport = AsyncMock()
        transport.transport_name = "test"

        msg = InboundMessage(
            tenant_id="t1",
            text="",
            channel_id="ch1",
            reply_transport=transport,
            media_type="photo",
            media_bytes=b"image-data",
            media_caption="my photo",
        )
        assert msg.media_type == "photo"
        assert msg.media_bytes == b"image-data"
        assert msg.media_caption == "my photo"

    def test_frozen(self) -> None:
        transport = AsyncMock()
        transport.transport_name = "test"

        msg = InboundMessage(tenant_id="t1", text="hi", channel_id="ch1", reply_transport=transport)
        with pytest.raises(AttributeError):
            msg.text = "changed"  # type: ignore[misc]


class TestButton:
    def test_creation(self) -> None:
        btn = Button(label="Approve", callback_data="approve:skill:test:v1")
        assert btn.label == "Approve"
        assert btn.callback_data == "approve:skill:test:v1"
