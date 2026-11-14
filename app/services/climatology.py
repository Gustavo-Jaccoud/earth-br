from collections.abc import Iterable
from datetime import date, timedelta
from typing import Literal

import pandas as pd

NORMAL_YEARS = range(2001, 2021)  # normal climatológica 2001-2020
MAX_MISSING_FRACTION = 0.2


def window(series: pd.Series, end: date, days: int, agg: Literal["sum", "mean"]) -> float | None:
    """Soma ou média dos `days` dias terminando em `end`.

    None se mais de 20% da janela estiver sem dado. Com falhas toleradas, a soma é escalada
    pelos dias válidos (média × days).
    """
    index = pd.date_range(end - timedelta(days=days - 1), end)
    valid = series.reindex(index).dropna()
    if len(valid) < days * (1 - MAX_MISSING_FRACTION):
        return None
    mean = float(valid.mean())
    return mean * days if agg == "sum" else mean


def same_day_in(end: date, year: int) -> date:
    try:
        return end.replace(year=year)
    except ValueError:  # 29/02 em ano não bissexto
        return end.replace(year=year, day=28)


def normal(series: pd.Series, end: date, days: int, years: Iterable[int],
           agg: Literal["sum", "mean"]) -> float | None:
    """Média da mesma janela (mesmo dia/mês de `end`) nos `years` informados."""
    values = [window(series, same_day_in(end, y), days, agg) for y in years]
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None
