"""Monthly climate series (rain, soil moisture, temperature) against the 2001-2020 normal."""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.services import climatology

# variable id -> (POWER column, unit, aggregation, scale)
VARIABLES = {
    "rain": ("PRECTOTCORR", "mm", "sum", 1.0),
    "soil_moisture": ("GWETROOT", "%", "mean", 100.0),
    "temperature": ("T2M", "°C", "mean", 1.0),
}
MIN_COVERAGE = 0.8  # share of the month's days needed to call it complete


@dataclass
class Month:
    label: str  # YYYY-MM
    value: float | None
    complete: bool


def _aggregate(series: pd.Series, agg: str, scale: float) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.sum() if agg == "sum" else valid.mean()) * scale


def normals(history: pd.DataFrame, years: Iterable[int] = climatology.NORMAL_YEARS
            ) -> dict[str, dict[int, float]]:
    """variable -> {calendar month -> 2001-2020 normal} (monthly total for rain, mean for the
    others)."""
    data = history[history.index.year.isin(list(years))]
    out = {}
    for name, (column, _, agg, scale) in VARIABLES.items():
        by_month = data[column].groupby([data.index.year, data.index.month])
        per_year = (by_month.sum() if agg == "sum" else by_month.mean()) * scale
        out[name] = {int(m): float(v) for m, v in per_year.groupby(level=1).mean().items()}
    return out


def last_months(data: pd.DataFrame, reference: date, months: int) -> dict[str, list[Month]]:
    """The `months` calendar months ending at the reference month, oldest first."""
    periods = pd.period_range(end=pd.Period(reference, freq="M"), periods=months, freq="M")
    out = {name: [] for name in VARIABLES}
    for period in periods:
        chunk = data[(data.index >= period.start_time) & (data.index <= period.end_time)]
        for name, (column, _, agg, scale) in VARIABLES.items():
            value = _aggregate(chunk[column], agg, scale) if len(chunk) else None
            complete = len(chunk[column].dropna()) >= period.days_in_month * MIN_COVERAGE
            out[name].append(Month(label=str(period), value=value, complete=complete))
    return out
