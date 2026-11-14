from datetime import date

from pydantic import BaseModel


class DailyValue(BaseModel):
    date: date
    value: float | None


class ClimateSeries(BaseModel):
    variable: str
    unit: str
    source: str
    values: list[DailyValue]


class ClimateResponse(BaseModel):
    plot_id: int
    start: date
    end: date
    series: list[ClimateSeries]
