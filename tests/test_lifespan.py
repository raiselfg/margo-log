import unittest
from unittest.mock import AsyncMock, patch

from app.core.config import Settings
from app.main import create_app


class LifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_service_and_closes_bot(self):
        settings = Settings(
            _env_file=None,
            telegram_bot_token="123456789:test_token",
            telegram_chat_id=123,
        )
        bot = AsyncMock()
        with patch("app.main.Bot", return_value=bot):
            app = create_app(settings)
            async with app.router.lifespan_context(app):
                self.assertIsNotNone(app.state.message_service)
                bot.session.close.assert_not_awaited()
            bot.session.close.assert_awaited_once()