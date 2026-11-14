from typing import Literal

from pydantic import BaseModel

from app.models.climate import DailyValue


class SatelliteSeries(BaseModel):
    plot_id: int
    layer: Literal["ndvi", "soil_moisture", "precipitation"]
    unit: str
    source: str
    values: list[DailyValue]
