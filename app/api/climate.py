from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_plot_or_404, get_power_client, get_rasters
from app.clients.power import POWER_PARAMS, POWER_UNITS, PowerClient, last_available_date
from app.config_loader import get_config
from app.models.climate import (
    ClimateResponse,
    ClimateSeries,
    DailyValue,
    MonthlyClimate,
    MonthlySeries,
    MonthlyValue,
)
from app.models.farms import Plot
from app.repositories.rasters import RasterStore
from app.services import geometry, monthly

router = APIRouter(tags=["clima"])

DEFAULT_DAYS = 90


@router.get("/plots/{plot_id}/climate")
def get_climate(
    start: date | None = None,
    end: date | None = None,
    plot: Plot = Depends(get_plot_or_404),
    power: PowerClient = Depends(get_power_client),
) -> ClimateResponse:
    lon, lat = plot.centroid
    df = power.recent(lat, lon)
    if end is None:
        end = last_available_date(df, "PRECTOTCORR")
    if start is None:
        start = end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise HTTPException(422, "The start date must be before the end date.")
    if start < df.index.min().date():
        df = pd.concat([power.history(lat, lon), df])
        df = df[~df.index.duplicated(keep="last")]
    df = df.reindex(pd.date_range(start, end))
    series = [
        ClimateSeries(
            variable=name,
            unit=POWER_UNITS[name],
            source="NASA POWER",
            values=[
                DailyValue(date=day.date(), value=None if pd.isna(v) else float(v))
                for day, v in df[name].items()
            ],
        )
        for name in POWER_PARAMS
    ]
    return ClimateResponse(plot_id=plot.id, start=start, end=end, series=series)


@router.get("/plots/{plot_id}/climate/monthly")
def get_monthly_climate(
    months: int = Query(12, ge=1, le=24),
    plot: Plot = Depends(get_plot_or_404),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
) -> MonthlyClimate:
    """Monthly values for the last `months` months, each next to the historical normal for that
    calendar month. NASA POWER: rain, root-zone soil moisture, mean and maximum air temperature,
    reference evapotranspiration (Hargreaves), water balance (rain minus evapotranspiration) and
    the longest run of dry days. Satellite (when the rasters exist): rain (GPM), soil moisture
    (SMAP) and NDVI (MODIS); the ones without data are listed in `unavailable`. The current
    month is partial (`complete: false`)."""
    lon, lat = plot.centroid
    dry_day_mm = get_config().signals.dry_day_mm
    recent = power.recent(lat, lon)
    reference = last_available_date(recent, "PRECTOTCORR")
    normals = monthly.normals(power.history(lat, lon), dry_day_mm=dry_day_mm)
    series = monthly.last_months(recent, reference, months, dry_day_mm)

    def values(items: list[monthly.Month], normal: dict[int, float]) -> list[MonthlyValue]:
        return [MonthlyValue(label=m.label, complete=m.complete,
                             value=None if m.value is None else round(m.value, 2),
                             normal=round(normal[int(m.label[5:])], 2)
                             if int(m.label[5:]) in normal else None) for m in items]

    variables = [
        MonthlySeries(variable=name, unit=unit, source="NASA POWER", normal_period="2001-2020",
                      months=values(series[name], normals[name]))
        for name, (_, unit, _, _) in monthly.VARIABLES.items()
    ]
    unavailable = []
    shape = geometry.to_shape(plot.geometry)
    for name, (layer, unit, agg, scale) in monthly.SATELLITE.items():
        daily = rasters.plot_series(layer, shape)
        if daily is None or daily.dropna().empty:
            unavailable.append(name)
            continue
        items, normal = monthly.satellite_months(daily, reference, months, agg, scale)
        variables.append(MonthlySeries(
            variable=name, unit=unit, source=rasters.meta(layer)["source"],
            normal_period=monthly.satellite_years(daily, reference),
            months=values(items, normal)))
    return MonthlyClimate(plot_id=plot.id, source="NASA POWER", reference_date=reference,
                          normal_period="2001-2020", variables=variables,
                          unavailable=unavailable)
