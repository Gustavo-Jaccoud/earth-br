from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_plot_or_404, get_power_client
from app.clients.power import POWER_PARAMS, POWER_UNITS, PowerClient, last_available_date
from app.models.climate import (
    ClimateResponse,
    ClimateSeries,
    DailyValue,
    MonthlyClimate,
    MonthlySeries,
    MonthlyValue,
)
from app.models.farms import Plot
from app.services import monthly

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
) -> MonthlyClimate:
    """Rain (monthly total, mm), root-zone soil moisture (%) and air temperature (°C) for the
    last `months` months, each next to the 2001-2020 normal for that calendar month. The current
    month is partial (`complete: false`)."""
    lon, lat = plot.centroid
    recent = power.recent(lat, lon)
    reference = last_available_date(recent, "PRECTOTCORR")
    normals = monthly.normals(power.history(lat, lon))
    series = monthly.last_months(recent, reference, months)
    variables = [
        MonthlySeries(variable=name, unit=unit, months=[
            MonthlyValue(label=m.label, complete=m.complete,
                         value=None if m.value is None else round(m.value, 2),
                         normal=round(normals[name][int(m.label[5:])], 2)
                         if int(m.label[5:]) in normals[name] else None)
            for m in series[name]])
        for name, (_, unit, _, _) in monthly.VARIABLES.items()
    ]
    return MonthlyClimate(plot_id=plot.id, source="NASA POWER", reference_date=reference,
                          normal_period="2001-2020", variables=variables)
