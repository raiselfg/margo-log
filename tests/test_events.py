import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx

from app.api.events import deliver_one
from app.main import create_app


class EventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = create_app()
        self.store = SimpleNamespace(save=AsyncMock(), claim=AsyncMock(return_value=None),
                                     finish=AsyncMock(), retry=AsyncMock())
        self.service = SimpleNamespace(send=AsyncMock(return_value=42))
        self.app.state.event_store = self.store
        self.app.state.message_service = self.service
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")
        self.payload = dict(event_id=str(uuid4()), session_id="session", sequence=1,
                            name="open", occurred_at="2026-10-15T12:00:00Z", text="test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_acceptance_confirms_persistence_not_telegram(self):
        response = await self.client.post("/api/v1/events", json=self.payload)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"ok": True, "event_id": self.payload["event_id"], "saved": True})
        self.store.save.assert_awaited_once()
        self.service.send.assert_not_awaited()

    async def test_database_failure_never_acknowledges_event(self):
        self.store.save.side_effect = RuntimeError("private DB connection string")
        response = await self.client.post("/api/v1/events", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private", response.text)
        self.store.claim.assert_not_awaited()

    async def test_unconfigured_database_is_explicit(self):
        self.app.state.event_store = None
        response = await self.client.post("/api/v1/events", json=self.payload)
        self.assertEqual(response.status_code, 503)

    async def test_new_event_retries_previously_queued_notification(self):
        item = dict(event_id=uuid4(), lease_token=uuid4(), text="previous event", attempts=2)
        self.store.claim.return_value = item
        response = await self.client.post("/api/v1/events", json=self.payload)
        self.assertEqual(response.status_code, 202)
        self.service.send.assert_awaited_once_with("previous event")
        self.store.finish.assert_awaited_once_with(item, 42)

    async def test_telegram_failure_requeues_and_does_not_mark_sent(self):
        item = dict(event_id=uuid4(), lease_token=uuid4(), text="hello", attempts=1)
        self.store.claim.return_value = item
        self.service.send.side_effect = RuntimeError("offline")
        self.assertFalse(await deliver_one(self.store, self.service))
        self.store.retry.assert_awaited_once_with(item)
        self.store.finish.assert_not_awaited()
        self.service.send.side_effect = None
        self.assertTrue(await deliver_one(self.store, self.service))
        self.store.finish.assert_awaited_once_with(item, 42)

    async def test_validation_happens_before_persistence(self):
        for changes in ({"event_id": "invalid"}, {"sequence": 0}, {"text": ""}, {"name": "bad name"}):
            response = await self.client.post("/api/v1/events", json=self.payload | changes)
            self.assertEqual(response.status_code, 422)
        self.store.save.assert_not_awaited()
