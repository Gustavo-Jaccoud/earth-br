"""PDF files of the reports, kept on disk so the document generated with the report can be
opened again later from My reports."""
from pathlib import Path

from app.models.farms import Farm, Plot
from app.models.reports import Report
from app.services import pdf


def path_for(var_dir: Path, report_id: int) -> Path:
    return Path(var_dir) / "reports" / f"{report_id}.pdf"


def save(var_dir: Path, report: Report, plot: Plot, farm: Farm | None) -> bytes:
    """Renders the PDF and stores it. A read-only disk is tolerated (the PDF is still returned)."""
    content = pdf.render_report(report, plot, farm)
    target = path_for(var_dir, report.id)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    except OSError:
        pass
    return content


def load_or_create(var_dir: Path, report: Report, plot: Plot, farm: Farm | None) -> bytes:
    target = path_for(var_dir, report.id)
    if target.exists():
        return target.read_bytes()
    return save(var_dir, report, plot, farm)
