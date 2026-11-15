"""Exporta um relatório em PDF (A4) com reportlab, usando só a fonte padrão (Helvetica).

Cada tipo de seção conhecido (sinais, rotação, aptidão, anos secos, risco, impacto financeiro,
sugestões) tem um desenho próprio; qualquer outro `data` cai num desenho genérico e seguro.
Cabeçalho e rodapé saem em todas as páginas ("Page X of Y" exige duas passagens no canvas).
"""
import re
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config_loader import get_config
from app.models.farms import Farm, Plot
from app.models.reports import Report, ReportSection
from app.services.dry_years import DROUGHT_ANOMALY_PCT

PRODUCT = "earth + BR"
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
DISCLAIMER = (
    "This report supports, and does not replace, the farmer's own judgment and the advice of "
    "local agronomists and extension services. The figures are estimates derived from public "
    "climate, satellite and crop-suitability datasets and may differ from the conditions "
    "observed in the field. earth + BR is a prototype.")
KIND_LABELS = {"analysis": "Land analysis report", "quiz": "Quick-start risk report"}

# Página: margens laterais iguais; faixas fixas para cabeçalho e rodapé.
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 2 * cm
MARGIN_TOP = 2.9 * cm
MARGIN_BOTTOM = 2.5 * cm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X
FRAME_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
LOGO_SIZE = 0.85 * cm
KEEP_WHOLE_SECTION = 0.45 * FRAME_HEIGHT  # seções menores que isto nunca são partidas
MAX_GENERIC_COLUMNS = 6
MAX_GENERIC_ROWS = 200

GREEN = colors.HexColor("#2f7d32")
DARK = colors.HexColor("#222222")
GRAY = colors.HexColor("#5f6368")
RULE = colors.HexColor("#c8d6c9")
HEADER_BG = colors.HexColor("#e6f1e6")
STRIPE_BG = colors.HexColor("#f6f9f6")
BOX_BG = colors.HexColor("#f3f6f3")
STATUS = {  # cor do sinal -> (rótulo, cor do texto)
    "green": ("Normal", "#2e7d32"), "yellow": ("Attention", "#b26a00"),
    "red": ("Critical", "#c62828"),
}
RISK_LEVELS = {"low": ("Low", "#2e7d32"), "medium": ("Medium", "#b26a00"),
               "high": ("High", "#c62828")}
SIGNAL_KINDS = {"rain": "Rainfall", "soil_moisture": "Root-zone soil moisture"}
CRITERIA = {"water": "Water supply", "soil": "Soil health", "suitability": "Crop suitability"}
UNIT_SUFFIXES = (("_brl_per_year", "R$/year"), ("_kg_ha", "kg/ha"), ("_pct", "%"), ("_mm", "mm"),
                 ("_ha", "ha"), ("_days", "days"))
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
REPLACEMENTS = {"→": "›", "←": "‹", "≥": ">=", "≤": "<=", "−": "-", "●": "•", "✓": "",
                " ": " ", " ": " ", " ": " "}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PAGE_OBJECT = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


def _style(name: str, **kw) -> ParagraphStyle:
    base = {"fontName": "Helvetica", "fontSize": 9.5, "leading": 13.5, "textColor": DARK}
    return ParagraphStyle(name, **{**base, **kw})


BODY = _style("body", spaceAfter=5)
BULLET = _style("bullet", leftIndent=12, bulletIndent=2, spaceAfter=3)
NOTE = _style("note", fontSize=8, leading=10.5, textColor=GRAY, spaceBefore=4, spaceAfter=2)
TITLE = _style("title", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=GREEN)
SUBTITLE = _style("subtitle", fontSize=9, leading=12, textColor=GRAY, spaceBefore=2,
                  spaceAfter=8)
HEADING = _style("heading", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=GREEN,
                 spaceBefore=14, spaceAfter=3)
SUBHEADING = _style("subheading", fontName="Helvetica-Bold", fontSize=9.5, spaceBefore=8,
                    spaceAfter=4, keepWithNext=1)
META_LABEL = _style("meta_label", fontSize=7.5, leading=10, textColor=GRAY)
META_VALUE = _style("meta_value", fontSize=9.5, leading=12.5)
CELL = _style("cell", fontSize=8.5, leading=11)
CELL_RIGHT = _style("cell_right", fontSize=8.5, leading=11, alignment=TA_RIGHT)
KEY = _style("key", fontSize=8.5, leading=11, textColor=GRAY)
HEAD = _style("head", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=GREEN)
HEAD_RIGHT = _style("head_right", fontName="Helvetica-Bold", fontSize=8.5, leading=11,
                    textColor=GREEN, alignment=TA_RIGHT)
DISCLAIMER_STYLE = _style("disclaimer", fontSize=8, leading=11, textColor=GRAY)


# --- texto e formatação de valores -------------------------------------------------------

def printable(text: str) -> str:
    """A fonte padrão só cobre Latin-1/Windows-1252: troca a seta e o que não couber por '?'."""
    text = str(text)
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("cp1252", errors="replace").decode("cp1252")


class _Markup(str):
    """Texto que já é markup do reportlab (escapado por quem o montou)."""


def _esc(text) -> str:
    return escape(printable(text))


def _p(text, style) -> Paragraph:
    if not isinstance(text, _Markup):
        text = _esc(text).replace("\n", "<br/>")
    return Paragraph(text, style)


def _colored(text: str, color: str) -> _Markup:
    return _Markup(f'<font color="{color}"><b>{_esc(text)}</b></font>')


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _is_scalar(value) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def fmt_number(value, decimals: int | None = None) -> str:
    """Número com separador de milhar; None vira "n/a"; o que não é número sai como texto."""
    if value is None:
        return "n/a"
    if not _is_number(value):
        return str(value)
    if decimals is None:
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:,.{decimals}f}"


def fmt_percent(value, decimals: int = 1, signed: bool = False) -> str:
    if not _is_number(value):
        return fmt_number(value)
    return f"{value:{'+' if signed else ''},.{decimals}f}%"


def fmt_date(value) -> str:
    """Data ISO (ou date) como "12 Nov 2026", sem depender do locale."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return f"{value.day} {MONTHS[value.month - 1][:3]} {value.year}"


def fmt_datetime(value: datetime) -> str:
    """O `created_at` é guardado em UTC: mostra sempre em UTC, com o rótulo."""
    value = value.astimezone(timezone.utc) if value.tzinfo else value
    return f"{fmt_date(value.date())}, {value:%H:%M} UTC"


def fmt_value(value) -> str:
    """Valor de `data` sem desenho próprio, em forma legível."""
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if _is_number(value):
        return fmt_number(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(fmt_value(v) for v in value)
    if isinstance(value, str) and ISO_DATE.match(value):
        return fmt_date(value)
    return str(value)


def fmt_signal_value(value, unit) -> str:
    """Valor de um sinal com a unidade; fração de saturação (unidade "1") vira percentual."""
    if not _is_number(value):
        return fmt_number(value)
    if unit in ("1", "fraction", None, ""):
        return f"{value * 100:.0f}%"
    return f"{fmt_number(value, 1 if unit == 'mm' else 2)} {unit}"


def fmt_months(months) -> str:
    """[4, 5, 6, 7, 8] -> "April–August"; meses não consecutivos saem separados por vírgula."""
    if not isinstance(months, (list, tuple)):
        return ""
    months = [m for m in months if isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 12]
    if not months:
        return ""
    names = [MONTHS[m - 1] for m in months]
    consecutive = all((b - a) % 12 == 1 for a, b in zip(months, months[1:], strict=False))
    if len(names) > 2 and consecutive:
        return f"{names[0]}–{names[-1]}"
    return ", ".join(names)


def label(key) -> str:
    """Nome de campo como título legível: "rain_anomaly_pct" -> "Rain anomaly (%)"."""
    key, unit = str(key), ""
    for suffix, text in UNIT_SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix):
            key, unit = key[: -len(suffix)], f" ({text})"
            break
    words = key.replace("_", " ").replace("-", " ").strip()
    return (words[:1].upper() + words[1:] + unit) if words else unit.strip()


def crop_name(crop_id) -> str:
    """Nome da cultura na configuração; id desconhecido sai legível ("abobora_doce")."""
    for crop in get_config().crops:
        if crop.id == crop_id:
            return crop.name
    return label(crop_id) if crop_id is not None else "n/a"


def crop_sequence(crops) -> str:
    if not isinstance(crops, (list, tuple)):
        return crop_name(crops)
    return " › ".join(crop_name(c) for c in crops)


def status_label(color) -> str:
    return STATUS[color][0] if color in STATUS else label(color)


def _status(color) -> _Markup:
    return _colored(status_label(color), STATUS[color][1]) if color in STATUS else _Markup(
        _esc(status_label(color)))


def collect_sources(sections) -> list[str]:
    """Fontes citadas nos campos `source` dos dados, na ordem em que aparecem, sem repetir.
    Um critério sem nota (`score` nulo) não usou a fonte e não a credita."""
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            source = node.get("source")
            unused = "score" in node and node["score"] is None
            if isinstance(source, str) and source.strip() and not unused:
                if source.strip() not in found:
                    found.append(source.strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    for section in sections:
        walk(section.data)
    return found


def footer_sources(sections) -> str:
    sources = collect_sources(sections)
    return f"Data sources: {', '.join(sources)}" if sources else ""


def page_count(pdf_bytes: bytes) -> int:
    """Número de páginas de um PDF gerado aqui (conta os objetos /Type /Page)."""
    return len(PAGE_OBJECT.findall(pdf_bytes))


# --- blocos de construção ----------------------------------------------------------------

def _dicts(value) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _table(headers: list[str], rows: list[list], widths: list[float], align: str) -> Table:
    """Tabela de largura total: células com quebra de linha, números à direita ("R" em `align`),
    cabeçalho repetido quando a tabela continua em outra página."""
    right = [a == "R" for a in align]
    data = [[_p(h, HEAD_RIGHT if r else HEAD) for h, r in zip(headers, right, strict=True)]]
    data += [[_p(cell, CELL_RIGHT if r else CELL) for cell, r in zip(row, right, strict=True)]
             for row in rows]
    total = sum(widths)
    table = Table(data, colWidths=[CONTENT_WIDTH * w / total for w in widths], repeatRows=1,
                  hAlign="LEFT", spaceBefore=4, spaceAfter=4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, STRIPE_BG]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, GREEN),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _key_values(pairs: list[tuple]) -> Table:
    """Pares rótulo/valor (sem cabeçalho), rótulo em cinza e valor com quebra de linha."""
    data = [[_p(k, KEY), _p(v, CELL)] for k, v in pairs]
    table = Table(data, colWidths=[CONTENT_WIDTH * 0.38, CONTENT_WIDTH * 0.62], hAlign="LEFT",
                  spaceBefore=4, spaceAfter=4)
    table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [STRIPE_BG, colors.white]),
        ("LINEABOVE", (0, 0), (-1, 0), 0.25, RULE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _text(text: str) -> list:
    """Corpo da seção: parágrafos; linhas iniciadas por "• " viram itens de lista."""
    flowables = []
    for line in str(text or "").split("\n"):
        line = line.strip()
        if line.startswith(("• ", "- ", "* ")):
            flowables.append(Paragraph(_esc(line[2:].strip()), BULLET, bulletText="•"))
        elif line:
            flowables.append(_p(line, BODY))
    return flowables


def _bullets(items) -> list:
    return [Paragraph(_esc(item), BULLET, bulletText="•") for item in items]


# --- seções conhecidas -------------------------------------------------------------------

def _signals(section: ReportSection) -> list:
    data = section.data
    rows = []
    for s in _dicts(data["signals"]):
        unit, days = s.get("unit"), s.get("window_days")
        rows.append([
            SIGNAL_KINDS.get(s.get("kind"), label(s.get("kind", ""))), _status(s.get("color")),
            fmt_signal_value(s.get("value"), unit), fmt_signal_value(s.get("normal"), unit),
            fmt_percent(s.get("deviation_pct"), signed=True),
            f"Last {days} days" if _is_number(days) else "n/a", fmt_value(s.get("source"))])
    flowables = _text(section.text)
    if rows:
        flowables.append(_table(
            ["Indicator", "Status", "Observed", "Average", "Difference", "Period", "Source"],
            rows, [23, 11, 11, 11, 12, 14, 18], "LLRRRLL"))
    if data.get("reference_date"):
        note = f"Reference date: {fmt_value(data['reference_date'])}"
        if data.get("reference_date_adjusted") is True:
            note += " (the requested date was moved back to the latest day with data)"
        flowables.append(_p(note + ".", NOTE))
    return flowables


def _rotation(section: ReportSection) -> list:
    options = _dicts(section.data["options"])
    rows, details = [], []
    for position, option in enumerate(options, start=1):
        scores = {s.get("name"): s for s in _dicts(option.get("scores"))}
        rank = option.get("rank", position)
        sequence = crop_sequence(option.get("crops"))
        rows.append([fmt_number(rank), sequence]
                    + [fmt_number(scores.get(name, {}).get("score"), 1) for name in CRITERIA]
                    + [_Markup(f"<b>{_esc(fmt_number(option.get('total'), 1))}</b>")])
        lines = [] if details else [_p("How each score was obtained", SUBHEADING)]
        lines.append(_p(_Markup(f"<b>{_esc(fmt_number(rank))}. {_esc(sequence)}</b>"), BODY))
        for name, score in scores.items():
            source = f" ({_esc(score['source'])})" if score.get("source") else ""
            lines.append(Paragraph(
                f"<b>{_esc(CRITERIA.get(name, label(name)))}{source}:</b> "
                f"{_esc(score.get('detail') or 'n/a')}", BULLET, bulletText="•"))
        if scores:
            details.append(KeepTogether(lines + [Spacer(1, 3)]))
    flowables = _text(section.text)
    if rows:
        flowables.append(_table(
            ["Rank", "Crop sequence", *CRITERIA.values(), "Total"], rows,
            [8, 38, 14, 13, 17, 10], "RLRRRR"))
        flowables.append(_p("Scores from 0 to 100; higher is better. n/a: no data for this "
                            "criterion at this field.", NOTE))
    if details:
        flowables += details
    return flowables


def _suitability(section: ReportSection) -> list:
    data = section.data
    rows = [[str(position), item.get("name") or crop_name(item.get("crop")),
             fmt_number(item.get("suitability"), 1),
             fmt_number(item.get("attainable_yield_kg_ha"), 0)]
            for position, item in enumerate(_dicts(data["items"]), start=1)]
    flowables = _text(section.text)
    if rows:
        flowables.append(_table(
            ["Rank", "Crop", "Suitability (0–100)", "Attainable yield (kg/ha, dry matter)"],
            rows, [8, 36, 24, 32], "RLRR"))
    notes = ["Rainfed conditions."]
    if isinstance(data.get("source"), str):
        period = f", {data['period']}" if isinstance(data.get("period"), str) else ""
        notes.append(f"Source: {data['source']}{period}.")
    without = data.get("without_data")
    if isinstance(without, list) and without:
        notes.append(f"No suitability data for: {', '.join(crop_name(c) for c in without)}.")
    flowables.append(_p(" ".join(notes), NOTE))
    return flowables


def _dry_years(section: ReportSection) -> list:
    data = section.data
    rows = []
    for year in _dicts(data["years"]):
        anomaly = year.get("rain_anomaly_pct")
        difference = fmt_percent(anomaly, signed=True)
        if _is_number(anomaly) and anomaly <= DROUGHT_ANOMALY_PCT:
            difference = _colored(difference, STATUS["red"][1])
        rows.append([fmt_value(year.get("year")) if not _is_number(year.get("year"))
                     else str(year["year"]), fmt_number(year.get("rain_mm"), 1), difference])
    flowables = _text(section.text)
    if rows:
        flowables.append(_table(
            ["Year", "Rainy-season rainfall (mm)", "Difference from normal"], rows,
            [20, 40, 40], "LRR"))
    notes = []
    season = fmt_months(data.get("rainy_season_months"))
    if season:
        notes.append(f"Rainy season: {season}.")
    if rows:
        notes.append(f"Years in red had rainfall at least {abs(DROUGHT_ANOMALY_PCT):.0f}% "
                     "below normal.")
    if isinstance(data.get("source"), str):
        notes.append(f"Source: {data['source']}.")
    if notes:
        flowables.append(_p(" ".join(notes), NOTE))
    return flowables


def _answer_rows(answers) -> list[list[str]]:
    """Perguntas e respostas do questionário com os textos da configuração."""
    if not isinstance(answers, dict):
        return []
    questions = {q.id: q for q in get_config().quiz.questions}
    rows = []
    for question_id, answer in answers.items():
        question = questions.get(question_id)
        labels = {o.id: o.label for o in question.options} if question else {}
        chosen = [labels.get(a, label(a)) for a in (answer if isinstance(answer, list)
                                                    else [answer])]
        if question and question.type == "rank":
            chosen = [f"{i}. {c}" for i, c in enumerate(chosen, start=1)]
        rows.append([question.text if question else label(question_id), ", ".join(chosen)])
    return rows


def _risk(section: ReportSection) -> list:
    data = section.data
    pairs = []
    if data.get("risk") is not None:
        risk = data["risk"]
        pairs.append(("Risk score", f"{fmt_number(risk)} out of 100" if _is_number(risk)
                      else fmt_value(risk)))
    level = data.get("level")
    if level is not None:
        pairs.append(("Risk level", _colored(*RISK_LEVELS[level]) if level in RISK_LEVELS
                      else label(level)))
    flowables = _text(section.text)
    if pairs:
        flowables.append(_key_values(pairs))
    rows = _answer_rows(data.get("answers"))
    if rows:
        flowables += [_p("Your answers", SUBHEADING),
                      _table(["Question", "Answer"], rows, [55, 45], "LL")]
    return flowables


def _financial(section: ReportSection) -> list:
    data = section.data
    pairs = []
    if _is_number(data.get("estimated_loss_brl_per_year")):
        pairs.append(("Estimated average loss per year",
                      f"R$ {fmt_number(data['estimated_loss_brl_per_year'], 0)}"))
    if data.get("crop") is not None:
        pairs.append(("Crop", crop_name(data["crop"])))
    if _is_number(data.get("attainable_yield_kg_ha")):
        pairs.append(("Attainable yield (dry matter)",
                      f"{fmt_number(data['attainable_yield_kg_ha'], 0)} kg/ha"))
    if _is_number(data.get("water_coverage_pct")):
        pairs.append(("Crop water need covered by rainfall",
                      fmt_percent(data["water_coverage_pct"])))
    flowables = _text(section.text)
    if pairs:
        flowables += [_key_values(pairs),
                      _p("Indicative estimate from historical rainfall and attainable yield; the "
                         "crop prices used are illustrative.", NOTE)]
    return flowables


def _suggestions(section: ReportSection) -> list:
    items = [s for s in section.data["suggestions"] if isinstance(s, str) and s.strip()]
    return _bullets(items) if items else _text(section.text)


def _generic(section: ReportSection) -> list:
    """Seção desconhecida: campos simples em pares rótulo/valor e listas de objetos em tabelas.
    Identificadores, textos que repetem o corpo e estruturas aninhadas ficam de fora."""
    flowables = _text(section.text)
    pairs, tables = [], []
    for key, value in section.data.items():
        key = str(key)
        if key == "id" or key.endswith("_id") or value == section.text:
            continue
        rows = _dicts(value)
        if rows:
            tables.append((key, rows))
        elif _is_scalar(value) or (isinstance(value, list) and value
                                   and all(_is_scalar(v) for v in value)):
            pairs.append((label(key), fmt_value(value)))
    if pairs:
        flowables.append(_key_values(pairs))
    for key, rows in tables:
        columns = []
        for row in rows:
            columns += [c for c in row if c not in columns and str(c) != "id"
                        and not str(c).endswith("_id") and _is_scalar(row[c])]
        columns = columns[:MAX_GENERIC_COLUMNS]
        if not columns:
            continue
        align = "".join("R" if all(_is_number(r.get(c)) or r.get(c) is None for r in rows)
                        and any(_is_number(r.get(c)) for r in rows) else "L" for c in columns)
        flowables += [_p(label(key), SUBHEADING), _table(
            [label(c) for c in columns],
            [[fmt_value(r.get(c)) for c in columns] for r in rows[:MAX_GENERIC_ROWS]],
            [1] * len(columns), align)]
        if len(rows) > MAX_GENERIC_ROWS:
            flowables.append(_p(f"Showing the first {MAX_GENERIC_ROWS} of {len(rows)} rows.",
                                NOTE))
    return flowables


def _renderer(data: dict):
    """Escolhe o desenho pela forma dos dados (não pelo título, que é texto livre)."""
    if isinstance(data.get("signals"), list):
        return _signals
    if isinstance(data.get("options"), list):
        return _rotation
    if isinstance(data.get("items"), list):
        return _suitability
    if isinstance(data.get("years"), list):
        return _dry_years
    if "risk" in data:
        return _risk
    if "estimated_loss_brl_per_year" in data:
        return _financial
    if isinstance(data.get("suggestions"), list):
        return _suggestions
    return _generic


def _section_body(section: ReportSection) -> list:
    """Nunca falha: dado inesperado cai no desenho genérico e, em último caso, só no texto."""
    data = section.data if isinstance(section.data, dict) else {}
    for render in (_renderer(data), _generic):
        try:
            return render(section)
        except Exception:  # noqa: BLE001 - o PDF tem de sair mesmo com dados fora do contrato
            continue
    return _text(section.text)


def _height(flowables: list) -> float:
    total = 0.0
    for flowable in flowables:
        total += flowable.wrap(CONTENT_WIDTH, FRAME_HEIGHT)[1]
        total += flowable.getSpaceBefore() + flowable.getSpaceAfter()
    return total


def _section(section: ReportSection) -> list:
    """Título + conteúdo. Seção pequena fica inteira na mesma página; a grande pode continuar
    na seguinte, mas o título só fica onde couber junto com o começo do conteúdo."""
    head = [_p(section.title, HEADING),
            HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=0, spaceAfter=6)]
    body = _section_body(section)
    try:
        if _height(head + body) <= KEEP_WHOLE_SECTION:
            return [KeepTogether(head + body)]
        lead = _height(head + body[:1])
        if body and isinstance(body[0], Paragraph) and len(body) > 1:
            lead += min(_height(body[1:2]), 3 * cm)  # texto + cabeçalho e 1ª linhas da tabela
        return [CondPageBreak(min(lead + 1.2 * cm, 0.6 * FRAME_HEIGHT))] + head + body
    except Exception:  # noqa: BLE001 - medir é só para paginar melhor
        return head + body


def _metadata(report: Report, plot: Plot, farm: Farm | None) -> Table:
    pairs = []
    if farm:
        pairs += [("PROPERTY", farm.name), ("LOCATION", f"{farm.municipality}, {farm.state}")]
    pairs += [
        ("FIELD", plot.name), ("FIELD AREA", f"{plot.area_ha:,.1f} ha"),
        ("CURRENT CROP", crop_name(plot.current_crop) if plot.current_crop else "Not informed"),
        ("GENERATED ON", fmt_datetime(report.created_at)),
    ]
    cells = [[_p(k, META_LABEL), _p(v, META_VALUE)] for k, v in pairs]
    rows = [[cells[i], cells[i + 1] if i + 1 < len(cells) else ""]
            for i in range(0, len(cells), 2)]
    table = Table(rows, colWidths=[CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4], spaceAfter=6)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BOX_BG),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, GREEN),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _disclaimer() -> KeepTogether:
    table = Table([[Paragraph(f"<b>Important.</b> {_esc(DISCLAIMER)}", DISCLAIMER_STYLE)]],
                  colWidths=[CONTENT_WIDTH])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BOX_BG), ("LINEBEFORE", (0, 0), (0, -1), 2, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return KeepTogether([Spacer(1, 16), table])


# --- cabeçalho, rodapé e numeração -------------------------------------------------------

def _fit(text: str, font: str, size: float, width: float) -> str:
    """Corta o texto com reticências para caber em `width`."""
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


class _ReportCanvas(Canvas):
    """Guarda as páginas e só as emite no fim, quando o total já é conhecido, desenhando em
    cada uma o mesmo cabeçalho (logo, produto, título) e rodapé (fontes, data, "Page X of Y")."""

    def __init__(self, *args, header_title: str = "", footer_lines: tuple[str, ...] = (),
                 **kwargs):
        super().__init__(*args, **kwargs)
        self._pages: list[dict] = []
        self._header_title = header_title
        self._footer_lines = footer_lines

    def showPage(self):  # noqa: N802 - API do reportlab
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self._chrome(total)
            super().showPage()
        super().save()

    def _chrome(self, total: int) -> None:
        self.saveState()
        right = PAGE_WIDTH - MARGIN_X
        # cabeçalho
        base = PAGE_HEIGHT - 1.95 * cm
        x = MARGIN_X
        if LOGO_PATH.is_file():
            self.drawImage(str(LOGO_PATH), x, base, width=LOGO_SIZE, height=LOGO_SIZE,
                           mask="auto", preserveAspectRatio=True)
            x += LOGO_SIZE + 6
        self.setFillColor(GREEN)
        self.setFont("Helvetica-Bold", 12)
        self.drawString(x, base + 7.5, PRODUCT)
        x += stringWidth(PRODUCT, "Helvetica-Bold", 12) + 1 * cm
        self.setFillColor(GRAY)
        self.setFont("Helvetica", 9)
        self.drawRightString(right, base + 8, _fit(self._header_title, "Helvetica", 9, right - x))
        self.setStrokeColor(GREEN)
        self.setLineWidth(0.8)
        self.line(MARGIN_X, base - 6, right, base - 6)
        # rodapé
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(MARGIN_X, 1.95 * cm, right, 1.95 * cm)
        self.setFont("Helvetica", 7.5)
        y = 1.55 * cm
        for line in self._footer_lines:
            self.drawString(MARGIN_X, y, line)
            y -= 0.34 * cm
        self.setFont("Helvetica", 8)
        self.drawRightString(right, 1.55 * cm, f"Page {self._pageNumber} of {total}")
        self.restoreState()


def _footer_lines(report: Report) -> tuple[str, ...]:
    """Fontes (no máximo duas linhas, ao lado da numeração) e a data de geração."""
    width = CONTENT_WIDTH - 3 * cm
    lines = simpleSplit(printable(footer_sources(report.sections)), "Helvetica", 7.5, width)
    if len(lines) > 2:
        lines = [lines[0], _fit(lines[1] + " …", "Helvetica", 7.5, width)]
    return (*lines, f"Generated on {fmt_datetime(report.created_at)} · {PRODUCT} prototype")


def render_report(report: Report, plot: Plot, farm: Farm | None = None) -> bytes:
    story = [_p(report.title, TITLE)]
    if report.kind in KIND_LABELS:
        story.append(_p(KIND_LABELS[report.kind], SUBTITLE))
    else:
        story.append(Spacer(1, 8))
    story.append(_metadata(report, plot, farm))
    for section in report.sections:
        story += _section(section)
    story.append(_disclaimer())

    title = printable(report.title)
    footer = _footer_lines(report)

    def canvas(*args, **kwargs) -> _ReportCanvas:
        return _ReportCanvas(*args, header_title=title, footer_lines=footer, **kwargs)

    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                      topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM, title=title,
                      author=PRODUCT).build(story, canvasmaker=canvas)
    return buffer.getvalue()
