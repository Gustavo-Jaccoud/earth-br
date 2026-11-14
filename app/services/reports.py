from datetime import date

from app.clients.power import PowerClient, PowerUnavailable
from app.models.farms import Farm, Plot
from app.models.reports import ReportSection
from app.models.rotation import RotationRequest
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.services import regional, rotation
from app.services.signals import NoDataForDate, build_signals
from app.services.texts import render

TOP_CROPS = 5


def unavailable_section(title: str) -> ReportSection:
    return ReportSection(title=title, text=render("report.unavailable"), data={})


def condition_section(plot, reference_date, power, rasters,
                      title: str = "Current conditions") -> ReportSection:
    try:
        signals = build_signals(plot, reference_date, power, rasters)
    except (PowerUnavailable, NoDataForDate):
        return unavailable_section(title)
    return ReportSection(title=title, text=" ".join(s.message for s in signals.signals),
                         data=signals.model_dump(mode="json"))


def _rotation(plot, farm, request, power, rasters, gaez) -> ReportSection:
    title = "Rotation comparison"
    try:
        result = rotation.compare(plot, farm, request, power, rasters, gaez)
    except PowerUnavailable:
        return unavailable_section(title)
    return ReportSection(title=title, text=result.verdict, data=result.model_dump(mode="json"))


def _suitability(plot, gaez) -> ReportSection:
    title = "Crop suitability"
    ranking = regional.suitability_ranking(plot, gaez)
    if not ranking.items:
        return unavailable_section(title)
    items = ", ".join(f"{i.name} ({i.suitability:.0f} out of 100)"
                      for i in ranking.items[:TOP_CROPS])
    return ReportSection(title=title, text=render("report.suitability", items=items),
                         data=ranking.model_dump(mode="json"))


def _dry_years(plot, power) -> ReportSection:
    title = "Dry years"
    try:
        result = regional.dry_years_report(plot, power)
    except PowerUnavailable:
        return unavailable_section(title)
    return ReportSection(title=title, text=result.message, data=result.model_dump(mode="json"))


def build_analysis(plot: Plot, farm: Farm, reference_date: date | None,
                   rotation_request: RotationRequest | None, power: PowerClient,
                   rasters: RasterStore, gaez: GaezRepository) -> list[ReportSection]:
    """Seções do relatório de análise. Uma fonte que falha vira "Dado indisponível no momento."
    na própria seção, sem derrubar o relatório. Cultura desconhecida na rotação (erro do
    cliente) sobe como UnknownCrop."""
    sections = [condition_section(plot, reference_date, power, rasters)]
    if rotation_request is not None:
        sections.append(_rotation(plot, farm, rotation_request, power, rasters, gaez))
    sections.append(_suitability(plot, gaez))
    sections.append(_dry_years(plot, power))
    return sections
