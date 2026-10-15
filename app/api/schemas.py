from pydantic import BaseModel, Field, field_validator


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be blank")
        if len(value.encode("utf-16-le")) // 2 > 4096:
            raise ValueError("Text must not exceed 4096 UTF-16 code units")
        return value


class SendMessageResponse(BaseModel):
    ok: bool = True
    message_id: int