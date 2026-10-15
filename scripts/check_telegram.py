"""Read-only Telegram configuration check: uv run python -m scripts.check_telegram."""
import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.core.config import Settings


async def main():
    settings = Settings()
    async with Bot(token=settings.telegram_bot_token.get_secret_value()) as bot:
        try:
            me = await bot.get_me(request_timeout=10)
            print(f"Bot token OK: @{me.username}")
            chat = await bot.get_chat(
                chat_id=settings.telegram_chat_id, request_timeout=10
            )
            print(f"Chat OK: type={chat.type}")
        except TelegramAPIError as exc:
            # Do not print request URLs, tokens or message contents.
            print(f"Telegram error: {type(exc).__name__}")
            if type(exc).__name__ == "TelegramBadRequest":
                print("Check TELEGRAM_CHAT_ID and send /start to your bot.")
            elif type(exc).__name__ == "TelegramUnauthorizedError":
                print("Check TELEGRAM_BOT_TOKEN.")
            elif type(exc).__name__ == "TelegramForbiddenError":
                print("Unblock the bot or grant it access to the chat.")
            else:
                print("Check the network connection and bot permissions.")
            raise SystemExit(1) from None


if __name__ == "__main__":
    asyncio.run(main())