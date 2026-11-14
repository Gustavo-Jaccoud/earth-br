import json
from datetime import date

import httpx
import numpy as np
import pytest
import respx

from app.clients.power import POWER_PARAMS, PowerClient, PowerUnavailable, last_available_date
from tests.helpers import FIXTURES, LAST_VALID_DAY, TODAY

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
RECENT_JSON = json.loads((FIXTURES / "power_recent.json").read_text())


def seeded(tmp_path, kind="recent", **kwargs):
    power = PowerClient(tmp_path, today=lambda: TODAY, **kwargs)
    path = power.cache_path(kind, -10.27, -37.05)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((FIXTURES / f"power_{kind}.json").read_text())
    return power


def test_fill_value_becomes_nan(tmp_path):
    df = seeded(tmp_path, live=False).recent(-10.27, -37.05)
    assert list(df.columns) == POWER_PARAMS
    assert np.isnan(df["PRECTOTCORR"].iloc[-1])
    assert (df.fillna(0) != -999).all().all()
    assert last_available_date(df, "PRECTOTCORR") == LAST_VALID_DAY


def test_history_uses_cache_without_network(tmp_path):
    power = seeded(tmp_path, kind="history", live=True)
    with respx.mock:  # qualquer chamada de rede falharia
        df = power.history(-10.27, -37.05)
    assert df.index[0] == np.datetime64("2001-01-01")
    assert len(df) > 8000


@respx.mock
def test_recent_falls_back_to_cache_on_error(tmp_path):
    respx.get(URL).mock(return_value=httpx.Response(500))
    df = seeded(tmp_path, live=True).recent(-10.27, -37.05)
    assert last_available_date(df, "PRECTOTCORR") == LAST_VALID_DAY


@respx.mock
def test_recent_without_cache_raises(tmp_path):
    respx.get(URL).mock(side_effect=httpx.ConnectError("sem internet"))
    with pytest.raises(PowerUnavailable):
        PowerClient(tmp_path, live=True, today=lambda: TODAY).recent(-10.27, -37.05)


def test_recent_not_live_without_cache_raises(tmp_path):
    with pytest.raises(PowerUnavailable):
        PowerClient(tmp_path, live=False, today=lambda: TODAY).recent(-10.27, -37.05)


@respx.mock
def test_recent_live_success_writes_cache_and_rounds_coordinates(tmp_path):
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=RECENT_JSON))
    power = PowerClient(tmp_path, live=True, today=lambda: TODAY)
    df = power.recent(-10.2649, -37.0451)
    params = route.calls.last.request.url.params
    assert params["latitude"] == "-10.26" and params["longitude"] == "-37.05"
    assert params["community"] == "AG"
    assert params["start"] == "20251010" and params["end"] == "20261114"  # 400 dias até hoje
    assert power.cache_path("recent", -10.2649, -37.0451).exists()
    assert last_available_date(df, "PRECTOTCORR") == date(2026, 11, 11)
