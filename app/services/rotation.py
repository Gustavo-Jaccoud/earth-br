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
from app.repositories.gaez import SOURCE as GAEZ
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.services import geometry, water
from app.services.texts import render


class UnknownCrop(ValueError):
    pass


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
            rasters: RasterStore | None, gaez: GaezRepository) -> RotationResponse:
    cfg = get_config()
    by_id = {c.id: c for c in cfg.crops}
    unknown = sorted({cid for option in request.options for cid in option if cid not in by_id})
    if unknown:
        raise UnknownCrop(
            f"Unknown crop: {', '.join(unknown)}. Valid crops: {', '.join(by_id)}."
        )

    lon, lat = plot.centroid
    clim = water.monthly_climatology(power.history(lat, lon))
    ndvi = _recent_ndvi(rasters, plot, cfg.rotation.ndvi_years)
    lo, hi = cfg.rotation.ndvi_range

    results = []
    for option in request.options:
        crops = [by_id[cid] for cid in option]
        water_pct = water.water_score(water.sequence_months(crops), clim)
        criteria = [CriterionScore(
            name="water", score=round(water_pct, 1), source="NASA POWER",
            detail=f"Historical rainfall covers {water_pct:.0f}% of the water the crop needs "
                   "during the growing months.")]

        if ndvi is None:
            criteria.append(CriterionScore(
                name="soil", score=None, source="NASA MODIS",
                detail="No vegetation vigor (NDVI) satellite data for this field yet."))
        else:
            soil = min(max((ndvi - lo) / (hi - lo), 0.0), 1.0) * 100
            note = ""
            if soil < 50 and any(c.soil_restoring for c in crops):
                soil = min(100.0, soil + cfg.rotation.soil_restoring_bonus)
                note = " Includes a bonus for a soil-restoring crop."
            criteria.append(CriterionScore(
                name="soil", score=round(soil, 1), source="NASA MODIS",
                detail=f"Recent average NDVI of {ndvi:.2f}.{note}"))

        found = [s for c in crops if (s := gaez.at(c.gaez_name, lat, lon))]
        if found:
            mean = sum(s for s, _ in found) / len(found)
            criteria.append(CriterionScore(
                name="suitability", score=round(mean, 1), source=GAEZ,
                detail=f"Average suitability of {mean:.0f} out of 100 for the local climate and "
                       f"soil, rainfed ({len(found)} of {len(crops)} crops with data)."))
        else:
            criteria.append(CriterionScore(
                name="suitability", score=None, source=GAEZ,
                detail="No GAEZ suitability data for these crops at this location."))

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
