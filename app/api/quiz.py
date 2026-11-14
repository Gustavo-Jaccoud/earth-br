from fastapi import APIRouter

from app.api import examples
from app.models.quiz import Question, QuizAnswers
from app.models.reports import Report

router = APIRouter(tags=["partida rápida"])


@router.get("/quiz")
def get_quiz() -> list[Question]:
    return examples.QUIZ


@router.post("/plots/{plot_id}/quiz", status_code=201)
def submit_quiz(plot_id: int, body: QuizAnswers) -> Report:
    return examples.REPORT
