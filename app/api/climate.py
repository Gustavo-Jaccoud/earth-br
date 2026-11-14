from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_plot_or_404, get_power_client
from app.clients.power import POWER_PARAMS, POWER_UNITS, PowerClient, last_available_date
from app.models.climate import ClimateResponse, ClimateSeries, DailyValue
from app.models.farms import Plot

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
        raise HTTPException(422, "A data inicial precisa ser anterior à data final.")
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
