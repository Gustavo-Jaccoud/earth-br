from fastapi import APIRouter, Response

from app.api import examples
from app.models.reports import AnalysisRequest, Report, ReportSummary

router = APIRouter(tags=["relatórios"])


@router.post("/plots/{plot_id}/reports/analysis", status_code=201)
def create_analysis_report(plot_id: int, body: AnalysisRequest | None = None) -> Report:
    return examples.REPORT


@router.get("/reports")
def list_reports(plot_id: int | None = None) -> list[ReportSummary]:
    return [examples.REPORT_SUMMARY]


@router.get("/reports/{report_id}")
def get_report(report_id: int) -> Report:
    return examples.REPORT


@router.get("/reports/{report_id}/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def get_report_pdf(report_id: int) -> Response:
    return Response(content=b"%PDF-1.4\n%exemplo\n", media_type="application/pdf")
