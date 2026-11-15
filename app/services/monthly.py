"""Monthly series against a historical normal: NASA POWER variables (measured and derived) and,
when the satellite rasters exist, satellite variables."""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from app.services import climatology
from app.services.water import et0_hargreaves

DRY_DAY_MM = 1.0  # a day with less rain than this counts as dry (default; see signals.yaml)

# variable id -> (column of the derived daily frame, unit, aggregation, scale)
VARIABLES = {
    "rain": ("rain", "mm", "sum", 1.0),
    "soil_moisture": ("soil", "%", "mean", 100.0),
    "temperature": ("temp", "°C", "mean", 1.0),
    "temperature_max": ("tmax", "°C", "mean", 1.0),
    "et0": ("et0", "mm", "sum", 1.0),
    "water_balance": ("balance", "mm", "sum", 1.0),
    "dry_spell": ("dry", "days", "longest_run", 1.0),
}
# variable id -> (raster layer, unit, aggregation, scale)
SATELLITE = {
    "rain_satellite": ("precipitation", "mm", "sum", 1.0),
    "soil_moisture_satellite": ("soil_moisture", "%", "mean", 100.0),
    "ndvi": ("ndvi", "", "mean", 1.0),
}
MIN_COVERAGE = 0.8  # share of the month's days needed to call it complete


@dataclass
class Month:
    label: str  # YYYY-MM
    value: float | None
    complete: bool


def derive(daily: pd.DataFrame, dry_day_mm: float = DRY_DAY_MM) -> pd.DataFrame:
    """Daily frame with one column per variable, from the raw NASA POWER columns. Missing
    inputs stay missing (NaN)."""
    def col(name: str) -> pd.Series:
        return daily[name] if name in daily else pd.Series(np.nan, index=daily.index)

    rain, tmax, tmin, temp, ra = (col(c) for c in ("PRECTOTCORR", "T2M_MAX", "T2M_MIN", "T2M",
                                                    "TOA_SW_DWN"))
    et0 = pd.Series([et0_hargreaves(a, b, c, d) if not np.isnan([a, b, c, d]).any() else np.nan
                     for a, b, c, d in zip(tmax, tmin, temp, ra, strict=True)], index=daily.index)
    dry = (rain < dry_day_mm).astype(float).where(rain.notna())
    return pd.DataFrame({"rain": rain, "soil": col("GWETROOT"), "temp": temp, "tmax": tmax,
                         "et0": et0, "balance": rain - et0, "dry": dry})


def _longest_run(series: pd.Series) -> float:
    """Longest run of consecutive 1s; a missing day breaks the run."""
    best = run = 0
    for value in series:
        run = run + 1 if value == 1 else 0
        best = max(best, run)
    return float(best)


def _aggregate(series: pd.Series, agg: str, scale: float) -> float | None:
    if series.dropna().empty:
        return None
    if agg == "longest_run":
        return _longest_run(series)
    valid = series.dropna()
    return float(valid.sum() if agg == "sum" else valid.mean()) * scale


def normals(history: pd.DataFrame, years: Iterable[int] = climatology.NORMAL_YEARS,
            dry_day_mm: float = DRY_DAY_MM) -> dict[str, dict[int, float]]:
    """variable -> {calendar month -> normal}: the mean, across the years, of each month's
    value (total for rain/ET0/balance, mean for the others, longest run for dry spells)."""
    data = derive(history[history.index.year.isin(list(years))], dry_day_mm)
    out = {}
    for name, (column, _, agg, scale) in VARIABLES.items():
        per_month = data[column].groupby([data.index.year, data.index.month]).apply(
            lambda chunk, agg=agg, scale=scale: _aggregate(chunk, agg, scale))
        per_month = per_month.dropna().astype(float)
        out[name] = {int(m): float(v) for m, v in per_month.groupby(level=1).mean().items()}
    return out


def last_months(data: pd.DataFrame, reference: date, months: int,
                dry_day_mm: float = DRY_DAY_MM) -> dict[str, list[Month]]:
    """The `months` calendar months ending at the reference month, oldest first."""
    derived = derive(data, dry_day_mm)
    periods = pd.period_range(end=pd.Period(reference, freq="M"), periods=months, freq="M")
    out = {name: [] for name in VARIABLES}
    for period in periods:
        chunk = derived[(derived.index >= period.start_time) & (derived.index <= period.end_time)]
        for name, (column, _, agg, scale) in VARIABLES.items():
            value = _aggregate(chunk[column], agg, scale) if len(chunk) else None
            complete = len(chunk[column].dropna()) >= period.days_in_month * MIN_COVERAGE
            out[name].append(Month(label=str(period), value=value, complete=complete))
    return out


def satellite_months(series: pd.Series, reference: date, months: int, agg: str, scale: float
                     ) -> tuple[list[Month], dict[int, float]]:
    """Monthly values of a satellite series for the months ending at the reference month, and
    the normal of each calendar month (mean over the earlier years in the raster)."""
    series = series.dropna()
    by_month = series.groupby([series.index.year, series.index.month]).apply(
        lambda chunk: _aggregate(chunk, agg, scale))
    last_day = series.index.max() if len(series) else None
    out = []
    for period in pd.period_range(end=pd.Period(reference, freq="M"), periods=months, freq="M"):
        value = by_month.get((period.year, period.month))
        complete = value is not None and last_day >= period.end_time.normalize()
        out.append(Month(label=str(period), value=None if value is None else float(value),
                         complete=bool(complete)))
    earlier = by_month[by_month.index.get_level_values(0) < reference.year]
    normal = {int(m): float(v) for m, v in earlier.groupby(level=1).mean().items()}
    return out, normal


def satellite_years(series: pd.Series, reference: date) -> str:
    """Years behind the satellite normal, e.g. "2015-2025"."""
    years = series.dropna().index.year
    years = years[years < reference.year]
    return f"{years.min()}-{years.max()}" if len(years) else ""
