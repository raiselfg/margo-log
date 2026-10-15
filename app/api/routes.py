from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_message_service
from app.api.schemas import SendMessageRequest, SendMessageResponse
from app.application.messages import MessageService
from app.domain.messages import MessageDeliveryError

router = APIRouter(prefix="/api/v1", tags=["messages"])


@router.post("/messages", response_model=SendMessageResponse)
async def send_message(
    payload: SendMessageRequest,
    service: Annotated[MessageService, Depends(get_message_service)],
) -> SendMessageResponse:
    try:
        message_id = await service.send(payload.text)
    except MessageDeliveryError:
        raise HTTPException(
            status_code=502, detail="Could not send message to Telegram"
        ) from None
    return SendMessageResponse(message_id=message_id)
