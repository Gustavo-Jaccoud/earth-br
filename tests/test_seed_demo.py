import json

import httpx
import respx

from app.clients.power import PowerClient
from pipeline import seed_demo
from tests.helpers import FIXTURES

HISTORY_JSON = json.loads((FIXTURES / "power_history.json").read_text())
RECENT_JSON = json.loads((FIXTURES / "power_recent.json").read_text())


def test_seed_is_idempotent(client):
    first = seed_demo.main(client=client)
    second = seed_demo.main(client=client)
    assert first == second and len(first) == 2
    farms = client.get("/farms").json()
    assert len(farms) == 1 and farms[0]["ibge_code"] == "2800209"
    plots = client.get(f"/farms/{farms[0]['id']}/plots").json()
    assert [p["id"] for p in plots] == first
    assert all(p["in_demo_region"] for p in plots)


def test_seed_survives_missing_power_data(client):
    # POWER sem cache e sem internet: o seed termina mesmo assim (só avisa).
    assert len(seed_demo.main(client=client)) == 2


def test_region_cells_cover_the_whole_bbox():
    cells = seed_demo.region_cells((-37.25, -10.45, -36.85, -10.10))
    assert set(cells) == {(-10.5, -37.5), (-10.5, -36.875), (-10.0, -37.5), (-10.0, -36.875)}


@respx.mock
def test_warm_power_cache_downloads_every_cell_once(tmp_path):
    def handler(request):
        history = request.url.params["start"] == "20010101"
        return httpx.Response(200, json=HISTORY_JSON if history else RECENT_JSON)

    route = respx.get("https://power.larc.nasa.gov/api/temporal/daily/point").mock(
        side_effect=handler)
    seed_demo.warm_power_cache(FIXTURES / "data", cache_dir=tmp_path)
    assert route.call_count == 8  # 4 células x (histórico + recente)
    assert len(list(tmp_path.glob("history_*.json"))) == 4
    assert len(list(tmp_path.glob("recent_*.json"))) == 4
    # um plot em qualquer ponto da região agora funciona sem internet
    power = PowerClient(tmp_path, live=False)
    assert not power.history(-10.15, -37.20).empty and not power.recent(-10.40, -36.90).empty


@respx.mock
def test_warm_power_cache_tolerates_failures(tmp_path, capsys):
    respx.get("https://power.larc.nasa.gov/api/temporal/daily/point").mock(
        return_value=httpx.Response(500))
    seed_demo.warm_power_cache(FIXTURES / "data", cache_dir=tmp_path)
    assert "AVISO" in capsys.readouterr().out
