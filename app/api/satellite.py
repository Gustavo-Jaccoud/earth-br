from datetime import date, timedelta
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_plot_or_404, get_rasters
from app.models.climate import DailyValue
from app.models.farms import Plot
from app.models.satellite import SatelliteSeries
from app.repositories.rasters import RasterStore
from app.services import geometry

router = APIRouter(tags=["satélite"])

NOT_AVAILABLE = (
    "Dados de satélite disponíveis apenas para a região de demonstração (Aquidabã/SE)."
)


@router.get("/plots/{plot_id}/satellite/{layer}")
def get_satellite(
    layer: Literal["ndvi", "soil_moisture", "precipitation"],
    start: date | None = None,
    end: date | None = None,
    plot: Plot = Depends(get_plot_or_404),
    rasters: RasterStore = Depends(get_rasters),
) -> SatelliteSeries:
    series = rasters.plot_series(layer, geometry.to_shape(plot.geometry))
    if series is None:
        raise HTTPException(404, NOT_AVAILABLE)
    end = end or series.index.max().date()
    start = start or end - timedelta(days=89)
    if start > end:
        raise HTTPException(422, "A data inicial precisa ser anterior à data final.")
    series = series[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]
    meta = rasters.meta(layer)
    return SatelliteSeries(
        plot_id=plot.id, layer=layer, unit=meta["units"], source=meta["source"],
        values=[DailyValue(date=day.date(), value=None if pd.isna(v) else float(v))
                for day, v in series.items()],
    )
