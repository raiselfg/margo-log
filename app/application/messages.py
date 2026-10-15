from app.domain.messages import MessageSender


class MessageService:
    def __init__(self, sender: MessageSender) -> None:
        self._sender = sender

    async def send(self, text: str) -> int:
        return await self._sender.send(text)