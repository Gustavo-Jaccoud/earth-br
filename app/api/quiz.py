from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_gaez,
    get_plot_or_404,
    get_power_client,
    get_rasters,
    get_report_repo,
)
from app.clients.power import PowerClient
from app.config_loader import get_config
from app.models.farms import Plot
from app.models.quiz import Question, QuizAnswers, QuizOption
from app.models.reports import Report
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.repositories.reports import ReportRepository
from app.services import quiz
from app.services.texts import render

router = APIRouter(tags=["partida rápida"])


@router.get("/quiz")
def get_quiz() -> list[Question]:
    """Perguntas da trilha (sem os pesos de risco e sugestões, que ficam no backend)."""
    return [
        Question(id=q.id, text=q.text, type=q.type, options=[QuizOption(id=o.id, label=o.label)
                                                for o in q.options])
        for q in get_config().quiz.questions
    ]


@router.post("/plots/{plot_id}/quiz", status_code=201)
def submit_quiz(
    body: QuizAnswers,
    plot: Plot = Depends(get_plot_or_404),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    gaez: GaezRepository = Depends(get_gaez),
    repo: ReportRepository = Depends(get_report_repo),
) -> Report:
    """Responde a trilha e devolve o relatório final: risco, impacto ambiental e financeiro
    e sugestões de contenção de danos."""
    try:
        sections = quiz.evaluate(plot, body, power, rasters, gaez)
    except quiz.QuizError as exc:
        raise HTTPException(422, str(exc)) from exc
    return repo.save(plot.id, "quiz", render("report.title_quiz", plot=plot.name), sections)
