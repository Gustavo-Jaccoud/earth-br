from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_farm_or_404_for_plot,
    get_ibge,
    get_plot_or_404,
    get_power_client,
    get_rasters,
    get_region,
    get_report_repo,
)
from app.clients.power import PowerClient
from app.config_loader import get_config
from app.models.farms import Farm, Plot
from app.models.quiz import Question, QuizAnswers, QuizOption
from app.models.reports import Report
from app.repositories.ibge import IbgeRepository
from app.repositories.rasters import RasterStore
from app.repositories.region import Region
from app.repositories.reports import ReportRepository
from app.services import quiz
from app.services.texts import render

router = APIRouter(tags=["partida rápida"])


@router.get("/quiz")
def get_quiz() -> list[Question]:
    """Perguntas da trilha (sem os pesos de risco e sugestões, que ficam no backend)."""
    return [
        Question(id=q.id, text=q.text, options=[QuizOption(id=o.id, label=o.label)
                                                for o in q.options])
        for q in get_config().quiz.questions
    ]


@router.post("/plots/{plot_id}/quiz", status_code=201)
def submit_quiz(
    body: QuizAnswers,
    plot: Plot = Depends(get_plot_or_404),
    farm: Farm = Depends(get_farm_or_404_for_plot),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    ibge: IbgeRepository = Depends(get_ibge),
    region: Region = Depends(get_region),
    repo: ReportRepository = Depends(get_report_repo),
) -> Report:
    """Responde a trilha e devolve o relatório final: risco, impacto ambiental e financeiro
    e sugestões de contenção de danos."""
    try:
        sections = quiz.evaluate(plot, farm, body, power, rasters, ibge, region)
    except quiz.QuizError as exc:
        raise HTTPException(422, str(exc)) from exc
    return repo.save(plot.id, "quiz", render("report.title_quiz", plot=plot.name), sections)
