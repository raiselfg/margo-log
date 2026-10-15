import logging
from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.events import EventStore, router as events_router
from app.api.routes import router
from app.api.middleware import RequestLoggingMiddleware
from app.core.logging import configure_logging
from app.application.messages import MessageService
from app.core.config import Settings
from app.infrastructure.telegram import TelegramMessageSender


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings if settings is not None else Settings()
        app.state.event_store = EventStore(config.database_url.get_secret_value()) if config.database_url else None
        bot = Bot(token=config.telegram_bot_token.get_secret_value())
        try:
            sender = TelegramMessageSender(bot, config.telegram_chat_id)
            app.state.message_service = MessageService(sender)
            logger.info("Application started | provider=telegram")
            yield
        finally:
            await bot.session.close()
            logger.info("Application stopped | telegram_session=closed")

    app = FastAPI(title="Margo notifications", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://super-secret-margo-1488.vercel.app"],
        allow_credentials=False,
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router)
    app.include_router(events_router)
    return app


app = create_app()
