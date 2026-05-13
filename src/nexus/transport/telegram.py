from __future__ import annotations

import html
import logging
import re
from collections.abc import Callable
from typing import Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from nexus.transport.base import Button, InboundMessage

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 4096


def _markdown_to_html(text: str) -> str:
    safe = html.escape(text)

    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"__(.+?)__", r"<u>\1</u>", safe)
    safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe)
    safe = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", safe)
    safe = re.sub(r"```(\w*)\n(.*?)```", r"<pre>\2</pre>", safe, flags=re.DOTALL)
    safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)
    safe = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', safe)

    return safe


class TelegramTransport:
    def __init__(
        self,
        bot_token: str,
        conversation_manager_send: Callable[..., Any],
        tenant_resolver: Callable[[str], str | None],
        webhook_url: str | None = None,
        webhook_port: int = 8443,
    ) -> None:
        self._bot_token = bot_token
        self._send_to_conv_manager = conversation_manager_send
        self._resolve = tenant_resolver
        self._webhook_url = webhook_url
        self._webhook_port = webhook_port
        self._app = (
            ApplicationBuilder()
            .token(bot_token)
            .connect_timeout(30.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .build()
        )
        self._bot = Bot(token=bot_token)

    @property
    def transport_name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        self._app.add_handler(CommandHandler("status", self._on_command))
        self._app.add_handler(CommandHandler("checkpoint", self._on_command))
        self._app.add_handler(CommandHandler("rollback", self._on_command))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        self._app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._on_voice))
        self._app.add_handler(MessageHandler(filters.PHOTO, self._on_photo))
        self._app.add_handler(MessageHandler(filters.Document.ALL, self._on_document))
        self._app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, self._on_video))
        self._app.add_handler(CallbackQueryHandler(self._on_callback))

        await self._app.initialize()
        await self._app.start()
        if self._webhook_url and self._app.updater:
            await self._app.updater.start_webhook(
                listen="0.0.0.0",
                port=self._webhook_port,
                url_path=self._bot_token,
                webhook_url=f"{self._webhook_url}/{self._bot_token}",
            )
            logger.info("Telegram transport started (webhook on port %d)", self._webhook_port)
        elif self._app.updater:
            await self._app.updater.start_polling()
            logger.info("Telegram transport started (polling)")

    async def stop(self) -> None:
        if self._app:
            if self._app.updater:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.message or not update.effective_chat:
            return

        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        inbound = InboundMessage(
            tenant_id=tenant_id,
            text=update.message.text or "",
            channel_id=str(update.effective_chat.id),
            reply_transport=self,
            message_id=str(update.message.message_id),
        )

        await self._send_to_conv_manager(
            {
                "action": "inbound_message",
                **inbound.to_payload(),
            }
        )

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or not update.effective_chat:
            return
        await query.answer()

        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            return

        await self._send_to_conv_manager(
            {
                "action": "callback",
                "tenant_id": tenant_id,
                "channel_id": str(update.effective_chat.id),
                "callback_data": query.data,
            }
        )

    async def _on_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.message or not update.effective_chat:
            return
        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        command = update.message.text or ""
        parts = command.split(maxsplit=1)
        cmd_name = parts[0].lstrip("/").split("@")[0]
        cmd_args = parts[1] if len(parts) > 1 else ""

        await self._send_to_conv_manager(
            {
                "action": "command",
                "tenant_id": tenant_id,
                "channel_id": str(update.effective_chat.id),
                "command": cmd_name,
                "args": cmd_args,
            }
        )

    async def _on_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.message or not update.effective_chat:
            return
        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        voice = update.message.voice or update.message.audio
        if not voice:
            return
        file = await voice.get_file()
        audio_bytes = bytes(await file.download_as_bytearray())

        inbound = InboundMessage(
            tenant_id=tenant_id,
            text="",
            channel_id=str(update.effective_chat.id),
            reply_transport=self,
            message_id=str(update.message.message_id),
            media_type="voice",
            media_bytes=audio_bytes,
        )
        await self._send_to_conv_manager(
            {
                "action": "inbound_message",
                **inbound.to_payload(),
            }
        )

    async def _on_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.message or not update.effective_chat:
            return
        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        photo = update.message.photo[-1] if update.message.photo else None
        if not photo:
            return
        file = await photo.get_file()
        image_bytes = bytes(await file.download_as_bytearray())

        inbound = InboundMessage(
            tenant_id=tenant_id,
            text=update.message.caption or "",
            channel_id=str(update.effective_chat.id),
            reply_transport=self,
            message_id=str(update.message.message_id),
            media_type="photo",
            media_bytes=image_bytes,
            media_caption=update.message.caption,
        )
        await self._send_to_conv_manager(
            {
                "action": "inbound_message",
                **inbound.to_payload(),
            }
        )

    async def _on_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.message or not update.effective_chat:
            return
        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        doc = update.message.document
        if not doc:
            return
        file = await doc.get_file()
        doc_bytes = bytes(await file.download_as_bytearray())

        inbound = InboundMessage(
            tenant_id=tenant_id,
            text=update.message.caption or "",
            channel_id=str(update.effective_chat.id),
            reply_transport=self,
            message_id=str(update.message.message_id),
            media_type="document",
            media_bytes=doc_bytes,
            metadata={"filename": doc.file_name or "document"},
        )
        await self._send_to_conv_manager(
            {
                "action": "inbound_message",
                **inbound.to_payload(),
            }
        )

    async def _on_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.message or not update.effective_chat:
            return
        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        video = update.message.video or update.message.video_note
        if not video:
            return
        file = await video.get_file()
        video_bytes = bytes(await file.download_as_bytearray())

        inbound = InboundMessage(
            tenant_id=tenant_id,
            text=update.message.caption or "",
            channel_id=str(update.effective_chat.id),
            reply_transport=self,
            message_id=str(update.message.message_id),
            media_type="video",
            media_bytes=video_bytes,
            media_caption=update.message.caption,
        )
        await self._send_to_conv_manager(
            {
                "action": "inbound_message",
                **inbound.to_payload(),
            }
        )

    async def send_text(self, channel_id: str, text: str) -> None:
        chat_id = int(channel_id)
        formatted = _markdown_to_html(text)

        for chunk in self._split_message(formatted):
            try:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                plain_chunk = self._split_message(text)[0] if chunk == formatted else chunk
                await self._bot.send_message(chat_id=chat_id, text=plain_chunk)

    @staticmethod
    def _split_message(text: str) -> list[str]:
        if len(text) <= _MAX_MESSAGE_LENGTH:
            return [text]
        chunks: list[str] = []
        while text:
            if len(text) <= _MAX_MESSAGE_LENGTH:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, _MAX_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = _MAX_MESSAGE_LENGTH
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks

    async def send_buttons(
        self,
        channel_id: str,
        text: str,
        buttons: list[Button],
    ) -> None:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(b.label, callback_data=b.callback_data) for b in buttons]]
        )
        await self._bot.send_message(
            chat_id=int(channel_id),
            text=text,
            reply_markup=keyboard,
        )

    async def send_typing(self, channel_id: str) -> None:
        await self._bot.send_chat_action(chat_id=int(channel_id), action="typing")
