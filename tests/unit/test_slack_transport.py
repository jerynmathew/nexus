from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import nexus.transport.slack as slmod
from nexus.transport.base import Button
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
        await t.send_buttons("C1", "Pick:", [Button(label="A", callback_data="a")])

    async def test_success(self) -> None:
        t, _, _ = _make_transport()
        t._app = MagicMock()
        t._app.client.chat_postMessage = AsyncMock()
        await t.send_buttons("C1", "Pick:", [Button(label="OK", callback_data="ok")])
        call_kwargs = t._app.client.chat_postMessage.call_args.kwargs
        assert "blocks" in call_kwargs
        assert call_kwargs["channel"] == "C1"


class TestStart:
    async def test_import_error(self) -> None:
        t, _, _ = _make_transport()
        with patch("nexus.transport.slack._HAS_SLACK", False):
            with pytest.raises(RuntimeError, match="slack-bolt"):
                await t.start()

    async def test_start_registers_handlers(self) -> None:
        t, _send_fn, _resolver = _make_transport()
        _, handlers = await _start_slack_with_handlers(t)
        assert "message" in handlers
        assert "app_mention" in handlers
        assert t._app is not None


async def _start_slack_with_handlers(t):
    mock_app = MagicMock()
    event_handlers = {}

    def mock_event(event_name):
        def decorator(fn):
            event_handlers[event_name] = fn
            return fn

        return decorator

    mock_app.event = mock_event

    mock_handler = AsyncMock()

    orig_has = slmod._HAS_SLACK
    slmod._HAS_SLACK = True
    old_async_app = getattr(slmod, "AsyncApp", None)
    old_handler = getattr(slmod, "AsyncSocketModeHandler", None)
    slmod.AsyncApp = MagicMock(return_value=mock_app)  # type: ignore[attr-defined]
    slmod.AsyncSocketModeHandler = MagicMock(return_value=mock_handler)  # type: ignore[attr-defined]

    try:
        await t.start()
    finally:
        slmod._HAS_SLACK = orig_has
        if old_async_app is not None:
            slmod.AsyncApp = old_async_app  # type: ignore[attr-defined]
        elif hasattr(slmod, "AsyncApp"):
            del slmod.AsyncApp  # type: ignore[attr-defined]
        if old_handler is not None:
            slmod.AsyncSocketModeHandler = old_handler  # type: ignore[attr-defined]
        elif hasattr(slmod, "AsyncSocketModeHandler"):
            del slmod.AsyncSocketModeHandler  # type: ignore[attr-defined]

    return mock_app, event_handlers


class TestMessageHandler:
    async def test_subtype_message_ignored(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _, handlers = await _start_slack_with_handlers(t)

        say = AsyncMock()
        await handlers["message"]({"subtype": "bot_message", "user": "U1"}, say)
        send_fn.assert_not_called()

    async def test_unauthorized_user(self) -> None:
        t, _send_fn, resolver = _make_transport()
        resolver.return_value = None
        _, handlers = await _start_slack_with_handlers(t)

        say = AsyncMock()
        await handlers["message"]({"user": "U_unknown", "text": "hello", "channel": "C1"}, say)
        say.assert_called_once_with("Sorry, you're not authorized.")

    async def test_valid_message(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _, handlers = await _start_slack_with_handlers(t)

        say = AsyncMock()
        await handlers["message"](
            {"user": "U1", "text": "hello world", "channel": "C123", "ts": "123.456"},
            say,
        )
        send_fn.assert_called_once()
        payload = send_fn.call_args[0][0]
        assert payload["action"] == "inbound_message"

    async def test_app_mention_delegates(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _, handlers = await _start_slack_with_handlers(t)

        say = AsyncMock()
        await handlers["app_mention"](
            {"user": "U1", "text": "hey bot", "channel": "C1", "ts": "1.1"},
            say,
        )
        send_fn.assert_called_once()


class TestSendTyping:
    async def test_no_op(self) -> None:
        t, _, _ = _make_transport()
        await t.send_typing("C1")
