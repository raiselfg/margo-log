import logging

from aiogram import Bot
from aiogram.exceptions import (TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramUnauthorizedError)

from app.domain.messages import MessageDeliveryError


logger = logging.getLogger(__name__)


class TelegramMessageSender:
    def __init__(self, bot: Bot, chat_id: int) -> None:
        self._bot = bot
        self._chat_id = chat_id

    async def send(self, text: str) -> int:
        try:
            message = await self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=None,
                request_timeout=10,
            )
        except TelegramAPIError as exc:
            reason = "Telegram rejected the request"
            if isinstance(exc, TelegramUnauthorizedError):
                reason = "Invalid bot token; check TELEGRAM_BOT_TOKEN"
            elif isinstance(exc, TelegramForbiddenError):
                reason = "Bot is blocked or has no permission to send to this chat"
            elif isinstance(exc, TelegramNetworkError):
                reason = "Cannot connect to Telegram; check network access"
            elif isinstance(exc, TelegramBadRequest):
                if "chat not found" in exc.message.lower():
                    reason = "Chat not found; check TELEGRAM_CHAT_ID and send /start to the bot"
                else:
                    reason = "Telegram rejected message parameters; check chat and text"
            logger.warning("Telegram delivery failed (%s): %s", type(exc).__name__, reason)
            raise MessageDeliveryError(reason) from exc
        return message.message_id