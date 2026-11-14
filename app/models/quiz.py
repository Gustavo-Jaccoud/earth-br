from pydantic import BaseModel


class QuizOption(BaseModel):
    id: str
    label: str


class Question(BaseModel):
    id: str
    text: str
    options: list[QuizOption]


class QuizAnswers(BaseModel):
    answers: dict[str, str]
