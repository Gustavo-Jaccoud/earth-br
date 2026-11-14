import pandas as pd

from app.clients.power import PowerClient
from app.config_loader import get_config
from app.models.farms import Farm, Plot
from app.models.rotation import (
    CriterionScore,
    RotationOptionResult,
    RotationRequest,
    RotationResponse,
)
from app.repositories.ibge import IbgeRepository
from app.repositories.rasters import RasterStore
from app.repositories.region import Region
from app.services import geometry, losses, water
from app.services.texts import render

STATE_CODES = {"MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26",
               "AL": "27", "SE": "28", "BA": "29"}


class UnknownCrop(ValueError):
    pass


def territory_codes(plot: Plot, farm: Farm, region: Region) -> tuple[str | None, str | None]:
    """(código IBGE do município, código da UF) usados para buscar a perda regional."""
    if farm.ibge_code:
        return farm.ibge_code, farm.ibge_code[:2]
    if plot.in_demo_region:
        return region.ibge_code, region.state_code
    return None, STATE_CODES.get(farm.state.upper())


def _recent_ndvi(rasters: RasterStore | None, plot: Plot, years: int) -> float | None:
    if rasters is None:
        return None
    series = rasters.plot_series("ndvi", geometry.to_shape(plot.geometry))
    if series is None or series.dropna().empty:
        return None
    recent = series[series.index >= series.index.max() - pd.DateOffset(years=years)]
    return float(recent.mean())


def _label(crops) -> str:
    return " → ".join(c.name for c in crops)


def compare(plot: Plot, farm: Farm, request: RotationRequest, power: PowerClient,
            rasters: RasterStore | None, ibge: IbgeRepository, region: Region
            ) -> RotationResponse:
    cfg = get_config()
    by_id = {c.id: c for c in cfg.crops}
    unknown = sorted({cid for option in request.options for cid in option if cid not in by_id})
    if unknown:
        raise UnknownCrop(
            f"Cultura desconhecida: {', '.join(unknown)}. Culturas válidas: {', '.join(by_id)}."
        )

    lon, lat = plot.centroid
    clim = water.monthly_climatology(power.history(lat, lon))
    ndvi = _recent_ndvi(rasters, plot, cfg.rotation.ndvi_years)
    municipality, state = territory_codes(plot, farm, region)
    lo, hi = cfg.rotation.ndvi_range

    results = []
    for option in request.options:
        crops = [by_id[cid] for cid in option]
        water_pct = water.water_score(water.sequence_months(crops), clim)
        criteria = [CriterionScore(
            name="water", score=round(water_pct, 1), source="NASA POWER",
            detail=f"A chuva histórica cobre {water_pct:.0f}% da água que a cultura precisa "
                   "nos meses de cultivo.")]

        if ndvi is None:
            criteria.append(CriterionScore(
                name="soil", score=None, source="NASA MODIS",
                detail="Sem dado de vigor da vegetação (NDVI) para este talhão: "
                       "satélite só na região de demonstração."))
        else:
            soil = min(max((ndvi - lo) / (hi - lo), 0.0), 1.0) * 100
            note = ""
            if soil < 50 and any(c.soil_restoring for c in crops):
                soil = min(100.0, soil + cfg.rotation.soil_restoring_bonus)
                note = " Inclui bônus por cultura que recupera o solo."
            criteria.append(CriterionScore(
                name="soil", score=round(soil, 1), source="NASA MODIS",
                detail=f"NDVI médio recente de {ndvi:.2f}.{note}"))

        found = [crop_loss for c in crops if c.ibge_name and (
            crop_loss := losses.crop_loss_pct(ibge, c.ibge_name, municipality, state))]
        if found:
            mean_loss = sum(pct for pct, _ in found) / len(found)
            criteria.append(CriterionScore(
                name="regional_loss", score=round(100 - mean_loss, 1), source="IBGE PAM",
                detail=f"Perda média de {mean_loss:.0f}% na região ({len(found)} de "
                       f"{len(crops)} culturas com dado)."))
        else:
            criteria.append(CriterionScore(
                name="regional_loss", score=None, source="IBGE PAM",
                detail="Sem dado do IBGE para estas culturas."))

        usable = [(cfg.rotation.weights[c.name], c.score) for c in criteria if c.score is not None]
        total = sum(w * s for w, s in usable) / sum(w for w, _ in usable)
        results.append((crops, criteria, round(total, 1)))

    results.sort(key=lambda r: r[2], reverse=True)
    options = [RotationOptionResult(crops=[c.id for c in crops], scores=criteria, total=total,
                                    rank=i)
               for i, (crops, criteria, total) in enumerate(results, start=1)]
    best_crops, _, best_total = results[0]
    return RotationResponse(
        plot_id=plot.id, options=options,
        verdict=render("rotation.verdict", best=_label(best_crops), total=f"{best_total:.1f}"),
    )
