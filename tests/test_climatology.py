from datetime import date

import numpy as np
import pandas as pd

from app.services.climatology import normal, window


def daily(start, end, value):
    index = pd.date_range(start, end)
    return pd.Series(value, index=index, dtype=float)


def test_window_sum_simple():
    assert window(daily("2020-01-01", "2020-03-01", 1.0), date(2020, 2, 10), 30, "sum") == 30.0


def test_window_mean_simple():
    assert window(daily("2020-01-01", "2020-03-01", 2.5), date(2020, 2, 10), 7, "mean") == 2.5


def test_window_none_when_mostly_nan():
    series = daily("2020-01-01", "2020-03-01", 1.0)
    series.loc["2020-01-20":"2020-02-10"] = np.nan  # janela de 30 dias quase toda vazia
    assert window(series, date(2020, 2, 10), 30, "sum") is None


def test_window_none_when_series_does_not_cover_window():
    assert window(daily("2020-02-01", "2020-03-01", 1.0), date(2020, 2, 10), 30, "sum") is None


def test_window_tolerates_up_to_20_percent_gaps():
    series = daily("2020-01-01", "2020-03-01", 1.0)
    series.loc["2020-02-01":"2020-02-05"] = np.nan  # 5 de 30 dias
    assert window(series, date(2020, 2, 10), 30, "sum") == 30.0  # escalado pelos dias válidos


def test_normal_cross_year_window():
    series = daily("2000-01-01", "2005-12-31", 1.0)
    assert normal(series, date(2010, 1, 10), 30, range(2001, 2006), "sum") == 30.0


def test_normal_leap_day_reference_uses_feb_28():
    series = daily("2000-01-01", "2005-12-31", 1.0)
    assert normal(series, date(2024, 2, 29), 7, range(2001, 2006), "sum") == 7.0


def test_normal_none_without_any_year():
    assert normal(daily("2020-01-01", "2020-03-01", 1.0), date(2020, 2, 10), 30,
                  range(2001, 2006), "sum") is None
