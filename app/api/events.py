"""Durable event intake and leased Telegram outbox."""
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import AwareDatetime, Field
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.api.schemas import SendMessageRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")
NOTIFY_EVENTS = {"visit", "open", "100", "gallery_open", "question_shown", "meeting_yes"}


class EventRequest(SendMessageRequest):
    event_id: UUID
    session_id: str = Field(min_length=1, max_length=100)
    sequence: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    occurred_at: AwareDatetime


class EventStore:
    def __init__(self, url: str):
        self.url = url

    async def connect(self):
        return await AsyncConnection.connect(self.url, row_factory=dict_row, connect_timeout=5)

    async def save(self, event: EventRequest):
        notify = event.name in NOTIFY_EVENTS
        async with await self.connect() as conn:
            await conn.execute(
                """INSERT INTO site_events (event_id, session_id, sequence, name, occurred_at, text, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (event_id) DO NOTHING""",
                (event.event_id, event.session_id, event.sequence, event.name, event.occurred_at,
                 event.text, "pending" if notify else "recorded"),
            )

    async def claim(self):
        token = uuid4()
        async with await self.connect() as conn:
            cursor = await conn.execute(
                """UPDATE site_events SET status='sending', lease_token=%s,
                    available_at=now() + interval '60 seconds', attempts=attempts+1
                WHERE event_id=(SELECT event_id FROM site_events
                    WHERE status IN ('pending', 'sending') AND available_at <= now()
                    ORDER BY received_at, sequence FOR UPDATE SKIP LOCKED LIMIT 1)
                RETURNING event_id, text, attempts, lease_token""", (token,),
            )
            return await cursor.fetchone()

    async def finish(self, item, message_id):
        async with await self.connect() as conn:
            await conn.execute(
                """UPDATE site_events SET status='sent', message_id=%s, sent_at=now(), lease_token=NULL
                WHERE event_id=%s AND lease_token=%s""",
                (message_id, item["event_id"], item["lease_token"]),
            )

    async def retry(self, item):
        delay = min(3600, 15 * 2 ** min(item["attempts"], 8))
        async with await self.connect() as conn:
            await conn.execute(
                """UPDATE site_events SET status='pending', lease_token=NULL,
                available_at=now() + %s * interval '1 second'
                WHERE event_id=%s AND lease_token=%s""",
                (delay, item["event_id"], item["lease_token"]),
            )


async def deliver_one(store, service):
    """One bounded attempt per invocation. The DB retains work after crashes."""
    try:
        item = await store.claim()
        if item is None:
            return False
        try:
            message_id = await service.send(item["text"])
        except Exception as exc:
            logger.warning("Outbox delivery deferred | event_id=%s error_type=%s", item["event_id"], type(exc).__name__)
            await store.retry(item)
            return False
        await store.finish(item, message_id)
        return True
    except Exception as exc:
        logger.error("Outbox worker failed | error_type=%s", type(exc).__name__)
        return False


@router.post("/events", status_code=202)
async def receive_event(payload: EventRequest, request: Request, tasks: BackgroundTasks):
    store = getattr(request.app.state, "event_store", None)
    if store is None:
        raise HTTPException(503, "Event database is not configured")
    try:
        await store.save(payload)
    except Exception as exc:
        logger.error("Event persistence failed | error_type=%s", type(exc).__name__)
        raise HTTPException(503, "Could not save event") from None
    tasks.add_task(deliver_one, store, request.app.state.message_service)
    return {"ok": True, "event_id": str(payload.event_id), "saved": True}

