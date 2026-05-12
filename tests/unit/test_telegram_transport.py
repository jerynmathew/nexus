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

    async def test_on_command_authorized(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.text = "/status"
        update.message.message_id = 1
        await t._on_command(update, None)
        call_payload = send_fn.call_args[0][0]
        assert call_payload["action"] == "command"
        assert call_payload["command"] == "status"

    async def test_on_command_with_args(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.text = "/checkpoint my-label"
        update.message.message_id = 1
        await t._on_command(update, None)
        call_payload = send_fn.call_args[0][0]
        assert call_payload["args"] == "my-label"

    async def test_on_command_unauthorized(self, transport):
        t, send_fn, resolver = transport
        resolver.return_value = None
        update = MagicMock()
        update.effective_user.id = 99999
        update.message.reply_text = AsyncMock()
        await t._on_command(update, None)
        update.message.reply_text.assert_called_once()
        send_fn.assert_not_called()

    async def test_on_voice(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        voice = MagicMock()
        file_obj = AsyncMock()
        file_obj.download_as_bytearray.return_value = bytearray(b"audio")
        voice.get_file = AsyncMock(return_value=file_obj)
        update.message.voice = voice
        update.message.audio = None
        await t._on_voice(update, None)
        call_payload = send_fn.call_args[0][0]
        assert call_payload["media_type"] == "voice"

    async def test_on_voice_unauthorized(self, transport):
        t, send_fn, resolver = transport
        resolver.return_value = None
        update = MagicMock()
        update.effective_user.id = 99
        update.message.reply_text = AsyncMock()
        await t._on_voice(update, None)
        send_fn.assert_not_called()

    async def test_on_voice_no_voice(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        update.message.voice = None
        update.message.audio = None
        await t._on_voice(update, None)
        send_fn.assert_not_called()

    async def test_on_photo(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        update.message.caption = "what is this?"
        photo = MagicMock()
        file_obj = AsyncMock()
        file_obj.download_as_bytearray.return_value = bytearray(b"img")
        photo.get_file = AsyncMock(return_value=file_obj)
        update.message.photo = [photo]
        await t._on_photo(update, None)
        call_payload = send_fn.call_args[0][0]
        assert call_payload["media_type"] == "photo"

    async def test_on_photo_no_photo(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        update.message.photo = []
        await t._on_photo(update, None)
        send_fn.assert_not_called()

    async def test_on_document(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        update.message.caption = ""
        doc = MagicMock()
        doc.file_name = "test.pdf"
        file_obj = AsyncMock()
        file_obj.download_as_bytearray.return_value = bytearray(b"pdf")
        doc.get_file = AsyncMock(return_value=file_obj)
        update.message.document = doc
        await t._on_document(update, None)
        call_payload = send_fn.call_args[0][0]
        assert call_payload["media_type"] == "document"

    async def test_on_document_no_doc(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        update.message.document = None
        await t._on_document(update, None)
        send_fn.assert_not_called()

    async def test_on_video(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        update.message.caption = ""
        video = MagicMock()
        file_obj = AsyncMock()
        file_obj.download_as_bytearray.return_value = bytearray(b"video")
        video.get_file = AsyncMock(return_value=file_obj)
        update.message.video = video
        update.message.video_note = None
        await t._on_video(update, None)
        call_payload = send_fn.call_args[0][0]
        assert call_payload["media_type"] == "video"

    async def test_on_video_no_video(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 67890
        update.message.message_id = 1
        update.message.video = None
        update.message.video_note = None
        await t._on_video(update, None)
        send_fn.assert_not_called()

    async def test_send_buttons(self, transport):
        t, _, _ = transport
        bot = AsyncMock()
        t._bot = bot
        from nexus.transport.base import Button

        await t.send_buttons("123", "Pick:", [Button(label="OK", callback_data="ok")])
        bot.send_message.assert_called_once()

    async def test_send_text_fallback_on_error(self, transport):
        t, _, _ = transport
        bot = AsyncMock()
        bot.send_message.side_effect = [Exception("parse error"), None]
        t._bot = bot
        await t.send_text("123", "Hello **world**")
        assert bot.send_message.call_count == 2

    def test_split_message_short(self, transport):
        t, _, _ = transport
        assert t._split_message("hi") == ["hi"]

    def test_split_message_long(self, transport):
        t, _, _ = transport
        text = "x" * 5000
        chunks = t._split_message(text)
        assert len(chunks) >= 2
        assert all(len(c) <= 4096 for c in chunks)

    async def test_on_text_no_user(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.effective_user = None
        await t._on_text(update, None)
        send_fn.assert_not_called()

    async def test_on_callback_no_query(self, transport):
        t, send_fn, _ = transport
        update = MagicMock()
        update.callback_query = None
        await t._on_callback(update, None)
        send_fn.assert_not_called()
