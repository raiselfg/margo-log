from typing import Protocol


class MessageDeliveryError(Exception):
    """The provider could not confirm delivery."""


class MessageSender(Protocol):
    async def send(self, text: str) -> int: ...