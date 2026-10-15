import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage

from app.api.dependencies import get_message_service
from app.application.messages import MessageService
from app.domain.messages import MessageDeliveryError
from app.infrastructure.telegram import TelegramMessageSender
from app.main import create_app


class MessageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sender = SimpleNamespace(send=AsyncMock(return_value=42))
        self.app = create_app()
        self.app.dependency_overrides[get_message_service] = lambda: MessageService(
            self.sender
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_cors_preflight_allows_frontend(self):
        origin = "https://super-secret-margo-1488.vercel.app"
        response = await self.client.options(
            "/api/v1/messages",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)
        self.assertIn("POST", response.headers["access-control-allow-methods"])
        self.assertIn(
            "content-type", response.headers["access-control-allow-headers"].lower()
        )
        self.assertNotIn("access-control-allow-credentials", response.headers)
        self.sender.send.assert_not_awaited()

    async def test_cors_preflight_rejects_other_origins(self):
        response = await self.client.options(
            "/api/v1/messages",
            headers={
                "Origin": "https://other.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)
        self.sender.send.assert_not_awaited()

    async def test_cors_headers_on_post_success_and_error(self):
        origin = "https://super-secret-margo-1488.vercel.app"
        for payload, status in (({"text": "hello"}, 200), ({"text": ""}, 422)):
            response = await self.client.post(
                "/api/v1/messages", json=payload, headers={"Origin": origin},
            )
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.headers["access-control-allow-origin"], origin)
        self.sender.send.assert_awaited_once_with("hello")

    async def test_delivers_payload_unchanged(self):
        text = "  Привет <b>мир</b>!\nНовая строка"
        response = await self.client.post("/api/v1/messages", json={"text": text})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "message_id": 42})
        self.sender.send.assert_awaited_once_with(text)

    async def test_rejects_invalid_payload_before_sending(self):
        for payload in ({}, {"text": ""}, {"text": " \n "},
                        {"text": "a" * 4097}, {"text": 123},
                        {"text": "😀" * 2049}):
            response = await self.client.post("/api/v1/messages", json=payload)
            self.assertEqual(response.status_code, 422)
        self.sender.send.assert_not_awaited()

    async def test_provider_failure_returns_generic_error(self):
        self.sender.send.side_effect = MessageDeliveryError("private details")
        response = await self.client.post("/api/v1/messages", json={"text": "hello"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(), {"detail": "Could not send message to Telegram"}
        )

    async def test_adapter_sends_plain_text(self):
        bot = AsyncMock(spec=Bot)
        bot.send_message.return_value = SimpleNamespace(message_id=9)
        self.assertEqual(await TelegramMessageSender(bot, -123).send("<b>hi</b>"), 9)
        bot.send_message.assert_awaited_once_with(
            chat_id=-123, text="<b>hi</b>", parse_mode=None, request_timeout=10
        )

    async def test_adapter_translates_errors(self):
        bot = AsyncMock(spec=Bot)
        bot.send_message.side_effect = TelegramBadRequest(
            method=SendMessage(chat_id=123, text="hello"), message="bad chat"
        )
        with self.assertRaises(MessageDeliveryError):
            await TelegramMessageSender(bot, 123).send("hello")


if __name__ == "__main__":
    unittest.main()