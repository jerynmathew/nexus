from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexus.transport.telegram import TelegramTransport


@pytest.fixture()
def transport():
    send_fn = AsyncMock()
    resolver = MagicMock(return_value="tenant_1")
    t = TelegramTransport(
        bot_token="fake-token",
        conversation_manager_send=send_fn,
        tenant_resolver=resolver,
    )
    return t, send_fn, resolver


class TestTelegramTransport:
    def test_transport_name(self, transport):
        t, _, _ = transport
        assert t.transport_name == "telegram"

    async def test_on_text_known_user(self, transport):
        t, send_fn, resolver = transport

        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.text = "hello"
        update.message.message_id = 1

        await t._on_text(update, None)

        resolver.assert_called_once_with("12345")
        send_fn.assert_called_once()
        call_payload = send_fn.call_args[0][0]
        assert call_payload["action"] == "inbound_message"
        assert call_payload["tenant_id"] == "tenant_1"
        assert call_payload["text"] == "hello"

    async def test_on_text_unknown_user(self, transport):
        t, send_fn, resolver = transport
        resolver.return_value = None

        update = MagicMock()
        update.effective_user.id = 99999
        update.message.reply_text = AsyncMock()

        await t._on_text(update, None)

        update.message.reply_text.assert_called_once_with("Sorry, you're not authorized.")
        send_fn.assert_not_called()

    async def test_on_callback(self, transport):
        t, send_fn, _resolver = transport

        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.callback_query.data = "approve:skill:test"
        update.callback_query.answer = AsyncMock()

        await t._on_callback(update, None)

        call_payload = send_fn.call_args[0][0]
        assert call_payload["action"] == "callback"
        assert call_payload["callback_data"] == "approve:skill:test"

    async def test_send_text(self, transport):
        t, _, _ = transport
        bot = AsyncMock()
        t._bot = bot

        await t.send_text("12345", "Hello world")

        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args
        assert call_kwargs.kwargs["chat_id"] == 12345
        assert call_kwargs.kwargs["text"] == "Hello world"

    async def test_send_typing(self, transport):
        t, _, _ = transport
        bot = AsyncMock()
        t._bot = bot

        await t.send_typing("12345")

        bot.send_chat_action.assert_called_once_with(chat_id=12345, action="typing")
