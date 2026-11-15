from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_farm_or_404_for_plot,
    get_gaez,
    get_plot_or_404,
    get_power_client,
    get_rasters,
    get_report_repo,
    get_var_dir,
)
from app.clients.power import PowerClient
from app.config_loader import get_config
from app.models.farms import Farm, Plot
from app.models.quiz import Question, QuizAnswers, QuizOption
from app.models.reports import Report
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.repositories.reports import ReportRepository
from app.services import pdf_store, quiz
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
    farm: Farm = Depends(get_farm_or_404_for_plot),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    gaez: GaezRepository = Depends(get_gaez),
    repo: ReportRepository = Depends(get_report_repo),
    var_dir: Path = Depends(get_var_dir),
) -> Report:
    """Responde a trilha e devolve o relatório final: risco, impacto ambiental e financeiro
    e sugestões de contenção de danos."""
    try:
        sections = quiz.evaluate(plot, farm, body, power, rasters, gaez)
    except quiz.QuizError as exc:
        raise HTTPException(422, str(exc)) from exc
    report = repo.save(plot.id, "quiz", render("report.title_quiz", plot=plot.name), sections)
    pdf_store.save(var_dir, report, plot, farm)  # the PDF is kept with the report
    return report
