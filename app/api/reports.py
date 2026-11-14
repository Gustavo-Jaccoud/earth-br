from fastapi import APIRouter, Depends, HTTPException, Response

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
from app.models.farms import Farm, Plot
from app.models.reports import AnalysisRequest, Report, ReportSummary
from app.repositories.ibge import IbgeRepository
from app.repositories.rasters import RasterStore
from app.repositories.region import Region
from app.repositories.reports import ReportRepository
from app.services import reports, rotation
from app.services.texts import render

router = APIRouter(tags=["relatórios"])


@router.post("/plots/{plot_id}/reports/analysis", status_code=201)
def create_analysis_report(
    body: AnalysisRequest | None = None,
    plot: Plot = Depends(get_plot_or_404),
    farm: Farm = Depends(get_farm_or_404_for_plot),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    ibge: IbgeRepository = Depends(get_ibge),
    region: Region = Depends(get_region),
    repo: ReportRepository = Depends(get_report_repo),
) -> Report:
    """Gera e salva o relatório de análise do talhão (condição atual, rotação opcional,
    perdas na região e causas ambientais)."""
    body = body or AnalysisRequest()
    try:
        sections = reports.build_analysis(plot, farm, body.reference_date, body.rotation, power,
                                          rasters, ibge, region)
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
        raise HTTPException(404, "Relatório não encontrado.")
    return report


@router.get("/reports/{report_id}/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def get_report_pdf(report_id: int) -> Response:
    return Response(content=b"%PDF-1.4\n%exemplo\n", media_type="application/pdf")
