"""Exporta um relatório em PDF (A4) com reportlab, usando só a fonte padrão (Helvetica)."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.farms import Farm, Plot
from app.models.reports import Report

FOOTER = "Fontes: NASA POWER, SMAP, GPM, MODIS; FAO GAEZ. Protótipo Field Shift."
MAX_TABLE_ROWS = 10
MAX_TABLE_COLUMNS = 6
MAX_CELL_CHARS = 40
GREEN = colors.HexColor("#2f7d32")
GRAY = colors.HexColor("#555555")


def printable(text: str) -> str:
    """A fonte padrão só cobre Latin-1/Windows-1252: troca a seta e o que não couber por '?'."""
    text = text.replace("→", "›")
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _p(text: str, style) -> Paragraph:
    return Paragraph(escape(printable(text)).replace("\n", "<br/>"), style)


def _is_scalar(value) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _flat(value) -> str | None:
    """Texto curto para escalares e listas de escalares (ex.: culturas); None se não couber."""
    if isinstance(value, list) and value and all(_is_scalar(v) for v in value):
        value = " › ".join(str(v) for v in value)
    if not _is_scalar(value):
        return None
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return text if len(text) <= MAX_CELL_CHARS else None  # textos longos já estão no corpo


def _data_tables(data: dict) -> list:
    """Campos curtos viram uma tabela chave/valor; listas de objetos viram tabelas pequenas."""
    flowables = []
    scalars = [(k, _flat(v)) for k, v in data.items() if not k.endswith("id")
               and not isinstance(v, list)]
    scalars = [(k, v) for k, v in scalars if v is not None]
    if scalars:
        flowables.append(_table([[k, printable(v)] for k, v in scalars]))
    for value in data.values():
        if isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
            columns = [c for c in value[0] if _flat(value[0][c]) is not None
                       and not c.endswith("id")][:MAX_TABLE_COLUMNS]
            if columns:
                rows = [columns] + [[printable(_flat(item.get(c)) or "") for c in columns]
                                    for item in value[:MAX_TABLE_ROWS]]
                flowables += [Spacer(1, 4), _table(rows, header=True)]
    return flowables


def _table(rows: list[list[str]], header: bool = False) -> Table:
    table = Table(rows, hAlign="LEFT")
    style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), GRAY),
             ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        style += [("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                  ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]
    table.setStyle(TableStyle(style))
    return table


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(2 * cm, 1.2 * cm, printable(FOOTER))
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def render_report(report: Report, plot: Plot, farm: Farm | None = None) -> bytes:
    sheet = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=sheet["Title"], textColor=GREEN, alignment=0)
    meta = ParagraphStyle("meta", parent=sheet["Normal"], textColor=GRAY, fontSize=9)
    heading = ParagraphStyle("heading", parent=sheet["Heading2"], textColor=GREEN)
    body = sheet["BodyText"]

    place = f" · {farm.name} · {farm.municipality}/{farm.state}" if farm else ""
    crop = f" · cultura atual: {plot.current_crop}" if plot.current_crop else ""
    story = [
        _p(report.title, title),
        _p(f"Gerado em {report.created_at:%d/%m/%Y %H:%M}", meta),
        _p(f"Talhão {plot.name} · {plot.area_ha:.1f} ha{crop}{place}", meta),
        Spacer(1, 12),
    ]
    for section in report.sections:
        story += [_p(section.title, heading), _p(section.text, body)]
        story += _data_tables(section.data)
        story.append(Spacer(1, 10))

    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=2 * cm, bottomMargin=2 * cm, title=printable(report.title)
                      ).build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
