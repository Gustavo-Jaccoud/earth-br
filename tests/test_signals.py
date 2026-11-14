import math
from datetime import date

import pandas as pd
import pytest

from app.config_loader import get_config
from app.services.signals import NoDataForDate, classify, rain_signal, soil_signal
from app.services.texts import render
from tests.helpers import LAST_VALID_DAY, install_power, make_layer, make_plot

NORMAL_YEARS = range(2001, 2006)
REFERENCE = date(2006, 6, 30)  # janela de chuva: 1 a 30 de junho


def synthetic(normal_total, recent_total, days=30):
    """1 valor por dia: cada janela de 30 dias soma normal_total nos anos normais e
    recent_total no ano de referência."""
    index = pd.date_range("2000-01-01", "2006-12-31")
    values = [recent_total / days if d.year == 2006 else normal_total / days for d in index]
    return pd.Series(values, index=index)


def test_classify_thresholds():
    t = get_config().signals.rain.pct
    assert classify(-10, t) == "green"
    assert classify(-20, t) == "yellow"
    assert classify(-50, t) == "red"
    assert classify(30, t) == "green"


def test_rain_red_when_well_below_normal():
    cfg = get_config().signals.rain
    signal = rain_signal(synthetic(100, 30), synthetic(100, 30), NORMAL_YEARS, REFERENCE,
                         cfg, "NASA POWER")
    assert signal.color == "red"
    assert signal.deviation_pct == -70.0
    assert (signal.value, signal.normal, signal.unit, signal.window_days) == (30.0, 100.0, "mm", 30)
    assert "30" in signal.message and signal.source == "NASA POWER"


def test_rain_green_when_close_to_normal():
    cfg = get_config().signals.rain
    signal = rain_signal(synthetic(100, 95), synthetic(100, 95), NORMAL_YEARS, REFERENCE,
                         cfg, "NASA POWER")
    assert signal.color == "green" and signal.deviation_pct == -5.0


def test_dry_season_uses_absolute_mode():
    cfg = get_config().signals.rain
    series = synthetic(5, 0)
    signal = rain_signal(series, series, NORMAL_YEARS, REFERENCE, cfg, "NASA POWER")
    assert signal.deviation_pct is None
    assert signal.color == "green"
    assert signal.message == render("rain.dry_season", value="0.0", days=30, normal="5.0")
    assert math.isfinite(signal.value) and math.isfinite(signal.normal)


def test_dry_season_absolute_deficit_turns_red():
    cfg = get_config().signals.rain  # normal 18 mm (< 20), choveu 0 -> déficit 18 > 15
    series = synthetic(18, 0)
    signal = rain_signal(series, series, NORMAL_YEARS, REFERENCE, cfg, "NASA POWER")
    assert signal.color == "red" and signal.deviation_pct is None
    assert "18 mm below" in signal.message


def test_rain_without_data_raises():
    cfg = get_config().signals.rain
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    with pytest.raises(NoDataForDate):
        rain_signal(empty, empty, NORMAL_YEARS, REFERENCE, cfg, "NASA POWER")


def test_soil_yellow_when_drier_than_normal():
    cfg = get_config().signals.soil_moisture
    index = pd.date_range("2000-01-01", "2006-12-31")
    series = pd.Series([0.45 if d.year == 2006 else 0.5 for d in index], index=index)
    signal = soil_signal(series, series, NORMAL_YEARS, REFERENCE, cfg, "NASA POWER")
    assert signal.color == "yellow" and signal.deviation_pct == -10.0
    assert signal.window_days == 7 and "45%" in signal.message


def test_api_signals_use_power_and_two_signals(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    body = client.get(f"/plots/{plot['id']}/signals").json()
    assert body["reference_date"] == LAST_VALID_DAY.isoformat()
    assert body["reference_date_adjusted"] is False
    assert [s["kind"] for s in body["signals"]] == ["rain", "soil_moisture"]
    assert all(s["source"] == "NASA POWER" for s in body["signals"])
    assert all(s["color"] in {"green", "yellow", "red"} for s in body["signals"])


def test_reference_date_clamped(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    response = client.get(f"/plots/{plot['id']}/signals?reference_date=2099-01-01")
    assert response.status_code == 200
    body = response.json()
    assert body["reference_date"] == LAST_VALID_DAY.isoformat()
    assert body["reference_date_adjusted"] is True


def test_reference_date_in_rainy_season_of_history(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    body = client.get(f"/plots/{plot['id']}/signals?reference_date=2022-06-30").json()
    assert body["reference_date"] == "2022-06-30" and body["reference_date_adjusted"] is False


def test_reference_date_without_data_422(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    response = client.get(f"/plots/{plot['id']}/signals?reference_date=2024-06-30")
    assert response.status_code == 422
    assert "reference date" in response.json()["detail"]


def test_offline_plot_elsewhere_in_region_uses_the_shared_cache(client, tmp_path):
    seeded = make_plot(client)
    install_power(client, tmp_path, seeded)  # cache só do 1º talhão
    elsewhere = [[-37.01, -10.31], [-37.00, -10.31], [-37.00, -10.30], [-37.01, -10.30],
                 [-37.01, -10.31]]  # ~4 km dali, mesma célula de ~50 km do POWER
    other = make_plot(client, elsewhere)
    assert other["centroid"] != seeded["centroid"]
    response = client.get(f"/plots/{other['id']}/signals")
    assert response.status_code == 200 and response.json()["signals"][0]["source"] == "NASA POWER"


def test_satellite_gap_at_reference_date_falls_back_to_power(client, tmp_path):
    from app.repositories.rasters import RasterStore

    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    make_layer(tmp_path, "precipitation", "2015-01-01", "2026-12-31", source="NASA GPM TESTE",
               nan_from="2026-10-01")
    make_layer(tmp_path, "soil_moisture", "2015-01-01", "2026-12-31", value=0.3,
               source="NASA SMAP TESTE", units="m3/m3", nan_from="2026-11-01")
    client.app.state.rasters = RasterStore(tmp_path)
    response = client.get(f"/plots/{plot['id']}/signals")
    assert response.status_code == 200
    assert [s["source"] for s in response.json()["signals"]] == ["NASA POWER", "NASA POWER"]


def test_no_data_message_lists_available_date_ranges(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    detail = client.get(f"/plots/{plot['id']}/signals?reference_date=2024-06-30").json()["detail"]
    assert "2001-01-01" in detail and "2023-12-31" in detail and "2025-10-10" in detail
    assert LAST_VALID_DAY.isoformat() in detail
