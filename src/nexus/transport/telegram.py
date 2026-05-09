from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from nexus.transport.base import Button, InboundMessage

logger = logging.getLogger(__name__)


class TelegramTransport:
    def __init__(
        self,
        bot_token: str,
        conversation_manager_send: Callable[..., Any],
        tenant_resolver: Callable[[str], str | None],
    ) -> None:
        self._bot_token = bot_token
        self._send_to_conv_manager = conversation_manager_send
        self._resolve = tenant_resolver
        self._app: Any = None
        self._bot: Any = None

    @property
    def transport_name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        from telegram import Bot
        from telegram.ext import (
            ApplicationBuilder,
            CallbackQueryHandler,
            MessageHandler,
            filters,
        )

        self._app = ApplicationBuilder().token(self._bot_token).build()
        self._bot = Bot(token=self._bot_token)

        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        self._app.add_handler(CallbackQueryHandler(self._on_callback))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        logger.info("Telegram transport started (polling)")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def _on_text(self, update: Any, context: Any) -> None:
        user_id = str(update.effective_user.id)
        tenant_id = self._resolve(user_id)
        if tenant_id is None:
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        inbound = InboundMessage(
            tenant_id=tenant_id,
            text=update.message.text,
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

    async def _on_callback(self, update: Any, context: Any) -> None:
        query = update.callback_query
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

    async def send_text(self, channel_id: str, text: str) -> None:
        if not self._bot:
            return
        from telegram.constants import ParseMode

        try:
            await self._bot.send_message(
                chat_id=int(channel_id),
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await self._bot.send_message(chat_id=int(channel_id), text=text)

    async def send_buttons(
        self,
        channel_id: str,
        text: str,
        buttons: list[Button],
    ) -> None:
        if not self._bot:
            return
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(b.label, callback_data=b.callback_data) for b in buttons]]
        )
        await self._bot.send_message(
            chat_id=int(channel_id),
            text=text,
            reply_markup=keyboard,
        )

    async def send_typing(self, channel_id: str) -> None:
        if not self._bot:
            return
        await self._bot.send_chat_action(chat_id=int(channel_id), action="typing")
