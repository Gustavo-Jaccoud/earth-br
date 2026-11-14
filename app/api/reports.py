from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import (
    get_farm_or_404_for_plot,
    get_farm_repo,
    get_gaez,
    get_plot_or_404,
    get_power_client,
    get_rasters,
    get_report_repo,
)
from app.clients.power import PowerClient
from app.models.farms import Farm, Plot
from app.models.reports import AnalysisRequest, Report, ReportSummary
from app.repositories.farms import FarmRepository
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.repositories.reports import ReportRepository
from app.services import pdf, reports, rotation
from app.services.texts import render

router = APIRouter(tags=["relatórios"])


@router.post("/plots/{plot_id}/reports/analysis", status_code=201)
def create_analysis_report(
    body: AnalysisRequest | None = None,
    plot: Plot = Depends(get_plot_or_404),
    farm: Farm = Depends(get_farm_or_404_for_plot),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    gaez: GaezRepository = Depends(get_gaez),
    repo: ReportRepository = Depends(get_report_repo),
) -> Report:
    """Gera e salva o relatório de análise do talhão (condição atual, rotação opcional,
    aptidão das culturas e anos secos)."""
    body = body or AnalysisRequest()
    try:
        sections = reports.build_analysis(plot, farm, body.reference_date, body.rotation, power,
                                          rasters, gaez)
    except rotation.UnknownCrop as exc:
        raise HTTPException(422, str(exc)) from exc
    return repo.save(plot.id, "analysis", render("report.title_analysis", plot=plot.name),
                     sections)


@router.get("/reports")
def list_reports(plot_id: int | None = None,
                 repo: ReportRepository = Depends(get_report_repo)) -> list[ReportSummary]:
    return repo.list(plot_id)


@router.get("/reports/{report_id}")
def get_report(report_id: int, repo: ReportRepository = Depends(get_report_repo)) -> Report:
    report = repo.get(report_id)
    if report is None:
        raise HTTPException(404, "Report not found.")
    return report


@router.get("/reports/{report_id}/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def get_report_pdf(
    report_id: int,
    repo: ReportRepository = Depends(get_report_repo),
    farms: FarmRepository = Depends(get_farm_repo),
) -> Response:
    """Relatório em PDF, pronto para baixar e compartilhar."""
    report = repo.get(report_id)
    if report is None:
        raise HTTPException(404, "Report not found.")
    plot = farms.get_plot(report.plot_id)
    farm = farms.get_farm(plot.farm_id) if plot else None
    return Response(
        content=pdf.render_report(report, plot, farm), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="relatorio-{report_id}.pdf"'},
    )
