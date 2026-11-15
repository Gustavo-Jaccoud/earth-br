from typing import Annotated

from pydantic import BaseModel, StringConstraints


class ChatMessage(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ChatAnswer(BaseModel):
    topic: str  # matched topic id, or "generic"
    answer: str
    used_data: bool  # False for fixed texts (no data, plain-text topics, generic answer)
    sources: list[str]
    suggestions: list[str]


class ChatIntro(BaseModel):
    greeting: str
    suggestions: list[str]
