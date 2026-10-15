from fastapi import Request

from app.application.messages import MessageService


def get_message_service(request: Request) -> MessageService:
    return request.app.state.message_service