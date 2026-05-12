from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from nexus.transport.slack import SlackTransport


def _make_transport():
    send_fn = AsyncMock()
    resolver = MagicMock(return_value="tenant_1")
    t = SlackTransport(
        bot_token="xoxb-fake",
        signing_secret="secret",
        conversation_manager_send=send_fn,
        tenant_resolver=resolver,
    )
    return t, send_fn, resolver


class TestInit:
    def test_stores_config(self) -> None:
        t, _, _ = _make_transport()
        assert t._bot_token == "xoxb-fake"
        assert t._signing_secret == "secret"
        assert t._port == 3002

    def test_transport_name(self) -> None:
        t, _, _ = _make_transport()
        assert t.transport_name == "slack"


class TestStop:
    async def test_with_handler(self) -> None:
        t, _, _ = _make_transport()
        t._handler = AsyncMock()
        await t.stop()
        t._handler.close_async.assert_called_once()

    async def test_no_handler(self) -> None:
        t, _, _ = _make_transport()
        t._handler = None
        await t.stop()


class TestSendText:
    async def test_no_app(self) -> None:
        t, _, _ = _make_transport()
        t._app = None
        await t.send_text("C123", "hello")

    async def test_success(self) -> None:
        t, _, _ = _make_transport()
        t._app = MagicMock()
        t._app.client.chat_postMessage = AsyncMock()
        await t.send_text("C123", "hello")
        t._app.client.chat_postMessage.assert_called_once_with(channel="C123", text="hello")


class TestSendButtons:
    async def test_no_app(self) -> None:
        t, _, _ = _make_transport()
        t._app = None
        from nexus.transport.base import Button

        await t.send_buttons("C1", "Pick:", [Button(label="A", callback_data="a")])

    async def test_success(self) -> None:
        t, _, _ = _make_transport()
        t._app = MagicMock()
        t._app.client.chat_postMessage = AsyncMock()
        from nexus.transport.base import Button

        await t.send_buttons("C1", "Pick:", [Button(label="OK", callback_data="ok")])
        call_kwargs = t._app.client.chat_postMessage.call_args.kwargs
        assert "blocks" in call_kwargs
        assert call_kwargs["channel"] == "C1"


class TestStart:
    async def test_import_error(self) -> None:
        from unittest.mock import patch

        t, _, _ = _make_transport()
        import pytest

        with patch("nexus.transport.slack._HAS_SLACK", False):
            with pytest.raises(RuntimeError, match="slack-bolt"):
                await t.start()


class TestSendTyping:
    async def test_no_op(self) -> None:
        t, _, _ = _make_transport()
        await t.send_typing("C1")
