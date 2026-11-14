import pandas as pd
import pytest

from app.config_loader import get_config
from app.models.crops import Crop
from app.services import water

CROPS = {c.id: c for c in get_config().crops}


def test_et0_known_value():
    assert water.et0_hargreaves(32, 22, 27, 39.5) == pytest.approx(5.25, abs=0.01)


def test_et0_never_negative_range():
    assert water.et0_hargreaves(20, 22, 21, 39.5) == 0.0  # tmax < tmin vira amplitude 0


def test_sequence_months_wraps_year():
    seq = water.sequence_months([CROPS["mandioca"], CROPS["feijao"]])
    feijao = [(m, kc) for crop, m, kc in seq if crop.id == "feijao"]
    assert feijao == [(4, 0.4), (5, 1.05), (6, 1.0)]  # mandioca (abril + 12 meses) termina em março


def test_sequence_months_second_crop_starts_after_first():
    seq = water.sequence_months([CROPS["milho"], CROPS["feijao"]])
    assert [m for c, m, _ in seq if c.id == "milho"] == [4, 5, 6, 7, 8]
    assert [m for c, m, _ in seq if c.id == "feijao"] == [9, 10, 11]


def test_monthly_climatology_totals():
    index = pd.date_range("2001-01-01", "2020-12-31")
    history = pd.DataFrame({"T2M_MAX": 32.0, "T2M_MIN": 22.0, "T2M": 27.0,
                            "TOA_SW_DWN": 39.5, "PRECTOTCORR": 1.0}, index=index)
    clim = water.monthly_climatology(history)
    assert list(clim.index) == list(range(1, 13))
    assert clim.loc[1, "rain_mm"] == pytest.approx(31.0)
    assert clim.loc[2, "rain_mm"] == pytest.approx(28.25)  # 5 anos bissextos em 20
    assert clim.loc[1, "et0_mm"] == pytest.approx(31 * 5.2515, rel=1e-3)


def clim(rain, et0):
    return pd.DataFrame({"rain_mm": rain, "et0_mm": et0}, index=range(1, 13))


def test_water_score_full_coverage():
    seq = water.sequence_months([CROPS["milho"], CROPS["feijao"]])
    assert water.water_score(seq, clim(300.0, 100.0)) == 100.0


def test_water_score_partial():
    crop = Crop(id="x", name="X", gaez_name=None, soil_restoring=False, planting_month=4,
                kc=[1.0, 1.0], price_brl_per_kg=None)
    assert water.water_score(water.sequence_months([crop]), clim(50.0, 100.0)) == 50.0


def test_yearly_coverage_shows_the_dry_year():
    index = pd.date_range("2001-01-01", "2003-12-31")
    rain = [0.5 if d.year == 2002 else 10.0 for d in index]
    history = pd.DataFrame({"T2M_MAX": 32.0, "T2M_MIN": 22.0, "T2M": 27.0, "TOA_SW_DWN": 39.5,
                            "PRECTOTCORR": rain}, index=index)
    coverage = water.yearly_coverage(water.sequence_months([CROPS["milho"]]), history,
                                     range(2001, 2004))
    assert coverage[2001] == 100.0 and coverage[2003] == 100.0
    assert coverage[2002] < 30
