"""Anos secos de um local: chuva da estação chuvosa (NASA POWER) contra a normal 2001-2020."""
from collections.abc import Iterable

import pandas as pd

from app.services import climatology

SEASON_MONTHS = 5
DROUGHT_ANOMALY_PCT = -20.0
TOP_YEARS = 3


def rainy_season(history: pd.DataFrame, years: Iterable[int] = climatology.NORMAL_YEARS
                 ) -> list[int]:
    """Os 5 meses consecutivos mais chuvosos do local (podem atravessar a virada do ano)."""
    rain = history["PRECTOTCORR"]
    rain = rain[rain.index.year.isin(list(years))]
    monthly = rain.groupby(rain.index.month).mean()  # mm/dia médio de cada mês
    windows = {start: [(start - 1 + i) % 12 + 1 for i in range(SEASON_MONTHS)]
               for start in range(1, 13)}
    best = max(windows, key=lambda s: sum(monthly.get(m, 0.0) for m in windows[s]))
    return windows[best]


def season_totals(history: pd.DataFrame, months: list[int]) -> dict[int, float]:
    """Chuva total (mm) de cada estação; a que atravessa o ano conta no ano em que começa.
    Só estações completas."""
    rain = history["PRECTOTCORR"].dropna()
    rain = rain[rain.index.month.isin(months)]
    wraps = months[0] > months[-1]
    season_year = rain.index.year - ((rain.index.month < months[0]) if wraps else 0)
    expected = {y: sum(pd.Period(year=y + (wraps and m < months[0]), month=m, freq="M")
                       .days_in_month for m in months) for y in set(season_year)}
    grouped = rain.groupby(season_year)
    return {int(y): float(total) for y, total in grouped.sum().items()
            if grouped.size()[y] >= expected[y] * 0.9}


def anomalies(history: pd.DataFrame, months: list[int],
              normal_years: Iterable[int] = climatology.NORMAL_YEARS) -> dict[int, float]:
    """Por ano: (chuva da estação − média nos anos normais) / média × 100."""
    totals = season_totals(history, months)
    normal = [totals[y] for y in normal_years if y in totals]
    base = sum(normal) / len(normal)
    return {year: (total - base) / base * 100 for year, total in totals.items()}
