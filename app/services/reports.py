from datetime import date

from app.clients.power import PowerClient, PowerUnavailable
from app.config_loader import get_config
from app.models.farms import Farm, Plot
from app.models.reports import ReportSection
from app.models.rotation import RotationRequest
from app.repositories.ibge import IbgeRepository
from app.repositories.rasters import RasterStore
from app.repositories.region import Region
from app.services import causes, losses, rotation
from app.services.signals import NoDataForDate, build_signals
from app.services.texts import render

TOP_LOSSES = 5
DEFAULT_CAUSES_CROP = "milho"


def _unavailable(title: str) -> ReportSection:
    return ReportSection(title=title, text=render("report.unavailable"), data={})


def _condition(plot, reference_date, power, rasters) -> ReportSection:
    title = "Condição atual"
    try:
        signals = build_signals(plot, reference_date, power, rasters)
    except (PowerUnavailable, NoDataForDate):
        return _unavailable(title)
    return ReportSection(title=title, text=" ".join(s.message for s in signals.signals),
                         data=signals.model_dump(mode="json"))


def _rotation(plot, farm, request, power, rasters, ibge, region) -> ReportSection:
    title = "Comparação de rotação"
    try:
        result = rotation.compare(plot, farm, request, power, rasters, ibge, region)
    except PowerUnavailable:
        return _unavailable(title)
    return ReportSection(title=title, text=result.verdict, data=result.model_dump(mode="json"))


def _regional_losses(plot, farm, ibge, region) -> ReportSection:
    title = "Perdas na região"
    _, state = rotation.territory_codes(plot, farm, region)
    rows = ibge.rows("state", state) if state else None
    if rows is None or rows.empty:
        return _unavailable(title)
    items = losses.ranking(rows, min_mean_planted_ha=losses.MIN_PLANTED_HA["state"])[:TOP_LOSSES]
    text = render("report.losses", territory=ibge.territory_name("state", state),
                  items=", ".join(f"{i.crop} ({i.mean_loss_pct:.0f}%)" for i in items))
    return ReportSection(title=title, text=text,
                         data={"items": [i.model_dump() for i in items]})


def _causes(plot, ibge, power, region) -> ReportSection:
    title = "Causas ambientais"
    crops = {c.id: c for c in get_config().crops}
    crop_id = plot.current_crop if (
        plot.current_crop in crops and crops[plot.current_crop].ibge_name) else DEFAULT_CAUSES_CROP
    try:
        result = causes.explain(crop_id, ibge, power, region)
    except (PowerUnavailable, causes.NoLossData):
        return _unavailable(title)
    return ReportSection(title=title, text=result.message, data=result.model_dump(mode="json"))


def build_analysis(plot: Plot, farm: Farm, reference_date: date | None,
                   rotation_request: RotationRequest | None, power: PowerClient,
                   rasters: RasterStore, ibge: IbgeRepository, region: Region
                   ) -> list[ReportSection]:
    """Seções do relatório de análise. Uma fonte que falha vira "Dado indisponível no momento."
    na própria seção, sem derrubar o relatório. Cultura desconhecida na rotação (erro do
    cliente) sobe como UnknownCrop."""
    sections = [_condition(plot, reference_date, power, rasters)]
    if rotation_request is not None:
        sections.append(_rotation(plot, farm, rotation_request, power, rasters, ibge, region))
    sections.append(_regional_losses(plot, farm, ibge, region))
    if plot.in_demo_region:
        sections.append(_causes(plot, ibge, power, region))
    return sections
