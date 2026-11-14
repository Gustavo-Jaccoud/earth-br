from typing import Literal

from pydantic import BaseModel


class QuizOption(BaseModel):
    id: str
    label: str


class Question(BaseModel):
    id: str
    text: str
    type: Literal["single", "multi", "rank"]
    options: list[QuizOption]


class QuizAnswers(BaseModel):
    """single: option id; multi: list of option ids; rank: all option ids, most important
    first."""
    answers: dict[str, str | list[str]]
