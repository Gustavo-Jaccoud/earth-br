import pandas as pd
import pytest

from app.services import dry_years


def history(daily_by_month, dry_year=None):
    index = pd.date_range("2001-01-01", "2020-12-31")
    rain = [daily_by_month[d.month] * (0.5 if d.year == dry_year else 1.0) for d in index]
    return pd.DataFrame({"PRECTOTCORR": rain}, index=index)


def test_rainy_season_is_wettest_five_month_window():
    wet = {m: (5.0 if m in (4, 5, 6, 7, 8) else 0.5) for m in range(1, 13)}
    assert dry_years.rainy_season(history(wet)) == [4, 5, 6, 7, 8]


def test_rainy_season_can_wrap_the_year():
    wet = {m: (5.0 if m in (11, 12, 1, 2, 3) else 0.5) for m in range(1, 13)}
    assert dry_years.rainy_season(history(wet)) == [11, 12, 1, 2, 3]


def test_season_totals_assign_wrapped_season_to_start_year():
    wet = {m: (1.0 if m in (11, 12, 1, 2, 3) else 0.0) for m in range(1, 13)}
    totals = dry_years.season_totals(history(wet), [11, 12, 1, 2, 3])
    assert totals[2001] == pytest.approx(30 + 31 + 31 + 28 + 31)
    assert 2020 not in totals  # estação 2020/21 incompleta


def test_anomalies_flag_the_dry_year():
    wet = {m: (5.0 if m in (4, 5, 6, 7, 8) else 0.5) for m in range(1, 13)}
    result = dry_years.anomalies(history(wet, dry_year=2012), [4, 5, 6, 7, 8])
    assert result[2012] == pytest.approx(-48.7, abs=0.1) and result[2013] > 0
