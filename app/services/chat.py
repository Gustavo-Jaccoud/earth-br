"""Demo assistant: picks a pre-written answer by keywords. There is no AI here."""
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from app.clients.power import PowerClient, last_available_date
from app.config_loader import ChatConfig, ChatTopic, get_config
from app.models.chat import ChatAnswer, ChatIntro
from app.models.farms import Farm, Plot
from app.models.rotation import RotationRequest
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.services import monthly, regional, rotation
from app.services.quiz import financial_section
from app.services.signals import build_signals


def normalize(text: str) -> list[str]:
    """Lowercase words without accents or punctuation."""
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", plain)


def _has(words: list[str], keyword: str) -> bool:
    """Whole word; prefix when the keyword ends in *; word sequence when it has spaces."""
    parts = keyword.split()
    for start in range(len(words) - len(parts) + 1):
        if all(words[start + i].startswith(p[:-1]) if p.endswith("*") else words[start + i] == p
               for i, p in enumerate(parts)):
            return True
    return False


def match(message: str, cfg: ChatConfig) -> ChatTopic | None:
    """Topic with the most keywords in the message. Ties go to the higher `priority`, then to
    the first listed. None when no keyword is found."""
    words = normalize(message)
    best, best_key = None, (0, 0)
    for topic in cfg.topics:
        score = sum(_has(words, keyword) for keyword in topic.keywords)
        if score and (score, topic.priority) > best_key:
            best, best_key = topic, (score, topic.priority)
    return best


def suggestions(cfg: ChatConfig, after: str | None, n: int = 3) -> list[str]:
    """Suggested questions from the topics that follow `after` in file order (wrapping)."""
    ids = [t.id for t in cfg.topics]
    start = ids.index(after) + 1 if after in ids else 0
    ordered = cfg.topics[start:] + cfg.topics[:start]
    return [t.question for t in ordered if t.question and t.id != after][:n]


# --------------------------------------------------------------------------------------------
# Answers: each data topic has a builder that returns the template fields, already formatted,
# or None when there is no data. Any failure falls back to the topic's fixed text.
# --------------------------------------------------------------------------------------------

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
SOURCES = "_sources"  # optional builder field: where the numbers actually came from
STATUS = {"green": "within the normal range", "yellow": "below average",
          "red": "well below average"}
SUMMARY = {0: "Neither indicator needs attention", 1: "One of the two indicators needs attention",
           2: "Both indicators need attention"}


@dataclass
class Context:
    plot: Plot
    farm: Farm
    power: PowerClient
    rasters: RasterStore
    gaez: GaezRepository


def _signal(ctx: Context, kind: str) -> dict[str, str]:
    result = build_signals(ctx.plot, None, ctx.power, ctx.rasters)
    signal = next(s for s in result.signals if s.kind == kind)
    return {"message": signal.message, "date": result.reference_date.isoformat(),
            SOURCES: [signal.source]}


def _temperature(ctx: Context) -> dict[str, str] | None:
    lon, lat = ctx.plot.centroid
    recent = ctx.power.recent(lat, lon)
    reference = last_available_date(recent, "T2M")
    months = monthly.last_months(recent, reference, 3)["temperature"]
    done = [m for m in months if m.complete and m.value is not None]
    if not done:
        return None
    latest = done[-1]
    normal = monthly.normals(ctx.power.history(lat, lon))["temperature"][int(latest.label[5:])]
    diff = latest.value - normal
    return {"month": f"{MONTHS[int(latest.label[5:]) - 1]} {latest.label[:4]}",
            "value": f"{latest.value:.1f}", "normal": f"{normal:.1f}", "diff": f"{abs(diff):.1f}",
            "direction": "above" if diff >= 0 else "below"}


def _risk(ctx: Context) -> dict[str, str]:
    result = build_signals(ctx.plot, None, ctx.power, ctx.rasters)
    by_kind = {s.kind: s for s in result.signals}
    alerts = sum(s.color != "green" for s in result.signals)
    return {"summary": SUMMARY[alerts], "rain_status": STATUS[by_kind["rain"].color],
            "soil_status": STATUS[by_kind["soil_moisture"].color],
            "date": result.reference_date.isoformat(),
            SOURCES: sorted({s.source for s in result.signals})}


def _dry_years(ctx: Context) -> dict[str, str]:
    result = regional.dry_years_report(ctx.plot, ctx.power)
    season = result.rainy_season_months
    return {"season": f"{MONTHS[season[0] - 1]} to {MONTHS[season[-1] - 1]}",
            "message": result.message}


def _crops(ctx: Context) -> dict[str, str] | None:
    items = regional.suitability_ranking(ctx.plot, ctx.gaez).items[:3]
    if not items:
        return None
    return {"items": ", ".join(f"{i.name} ({i.suitability:.0f} out of 100)" for i in items)}


def _rotation(ctx: Context) -> dict[str, str] | None:
    """Current crop against the best-suited non-legume followed by the best-suited legume."""
    crops = {c.id: c for c in get_config().crops}
    current = ctx.plot.current_crop
    ranked = [crops[i.crop] for i in regional.suitability_ranking(ctx.plot, ctx.gaez).items]
    main = next((c for c in ranked if not c.soil_restoring and c.id != current), None)
    legume = next((c for c in ranked if c.soil_restoring and c.id != current), None)
    if current not in crops or main is None or legume is None:
        return None
    result = rotation.compare(ctx.plot, ctx.farm,
                              RotationRequest(options=[[current], [main.id, legume.id]]),
                              ctx.power, ctx.rasters, ctx.gaez)
    totals = {tuple(o.crops): round(o.total) for o in result.options}
    current_total, alternative_total = totals[(current,)], totals[(main.id, legume.id)]
    verdict = ("Your current crop is already the best option for this field."
               if current_total >= alternative_total
               else "A rotation scores higher than your current crop on this field.")
    return {"verdict": verdict, "current": crops[current].name,
            "current_total": str(current_total),
            "alternative": f"{main.name} → {legume.name}",
            "alternative_total": str(alternative_total)}


def _financial(ctx: Context) -> dict[str, str] | None:
    section = financial_section(ctx.plot, ctx.power, ctx.gaez)
    return {"text": section.text} if section.data else None


BUILDERS: dict[str, Callable[[Context], dict | None]] = {
    "rain": lambda ctx: _signal(ctx, "rain"),
    "soil_moisture": lambda ctx: _signal(ctx, "soil_moisture"),
    "temperature": _temperature,
    "risk": _risk,
    "dry_years": _dry_years,
    "crops": _crops,
    "rotation": _rotation,
    "financial": _financial,
}


def _text(value: str) -> str:
    return " ".join(value.split())


def reply(message: str, ctx: Context) -> ChatAnswer:
    """Never raises for missing data: the topic's fixed text is used instead."""
    cfg = get_config().chat
    topic = match(message, cfg)
    if topic is None:
        return ChatAnswer(topic="generic", answer=_text(cfg.generic), used_data=False,
                          sources=[], suggestions=suggestions(cfg, None))
    answer, used_data, sources = None, False, topic.sources
    builder = BUILDERS.get(topic.id)
    if topic.answer and builder:
        try:
            fields = builder(ctx)
            if fields is not None:
                sources = fields.pop(SOURCES, topic.sources)
                answer, used_data = _text(topic.answer.format(**fields)), True
        except Exception:  # noqa: BLE001 — any data problem means the fixed text, never an error
            answer = None
    if answer is None:
        answer, used_data = _text(topic.fallback), False
    return ChatAnswer(topic=topic.id, answer=answer, used_data=used_data,
                      sources=sources if used_data else [],
                      suggestions=suggestions(cfg, topic.id))


def intro() -> ChatIntro:
    cfg = get_config().chat
    greeting = next(t.fallback for t in cfg.topics if t.id == "greeting")
    return ChatIntro(greeting=_text(greeting), suggestions=suggestions(cfg, None, 4))
