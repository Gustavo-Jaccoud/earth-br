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


class MonthlyValue(BaseModel):
    label: str  # YYYY-MM
    value: float | None
    normal: float | None  # 2001-2020 normal for that calendar month
    complete: bool  # False when the month still lacks data (e.g. the current month)


class MonthlySeries(BaseModel):
    # rain | soil_moisture | temperature | temperature_max | et0 | water_balance | dry_spell |
    # rain_satellite | soil_moisture_satellite | ndvi
    variable: str
    unit: str
    source: str
    normal_period: str  # years behind `normal`, e.g. "2001-2020"
    months: list[MonthlyValue]


class MonthlyClimate(BaseModel):
    plot_id: int
    source: str
    reference_date: date
    normal_period: str
    variables: list[MonthlySeries]
    unavailable: list[str]  # satellite variables with no data for this field yet
