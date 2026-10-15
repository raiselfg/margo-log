from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI

from app.api.routes import router
from app.application.messages import MessageService
from app.core.config import Settings
from app.infrastructure.telegram import TelegramMessageSender


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings if settings is not None else Settings()
        bot = Bot(token=config.telegram_bot_token.get_secret_value())
        try:
            sender = TelegramMessageSender(bot, config.telegram_chat_id)
            app.state.message_service = MessageService(sender)
            yield
        finally:
            await bot.session.close()

    app = FastAPI(title="Margo notifications", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
