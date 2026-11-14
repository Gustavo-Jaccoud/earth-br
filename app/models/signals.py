from datetime import date
from typing import Literal

from pydantic import BaseModel


class Signal(BaseModel):
    kind: Literal["rain", "soil_moisture"]
    color: Literal["green", "yellow", "red"]
    value: float
    normal: float
    deviation_pct: float | None
    unit: str
    window_days: int
    source: str
    message: str


class SignalsResponse(BaseModel):
    plot_id: int
    reference_date: date
    reference_date_adjusted: bool
    signals: list[Signal]
