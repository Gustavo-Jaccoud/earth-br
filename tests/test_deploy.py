import json
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient

from app.clients.power import PowerClient
from app.main import create_app
from app.settings import Settings
from tests.helpers import FIXTURES, TODAY

RECENT_JSON = json.loads((FIXTURES / "power_recent.json").read_text())
URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


def app_with(tmp_path, **kwargs):
    settings = Settings(data_dir=FIXTURES / "data", var_dir=tmp_path / "var", power_live=False,
                        **kwargs)
    return create_app(settings)


def test_seed_demo_creates_the_demo_property_on_an_empty_database(tmp_path):
    with TestClient(app_with(tmp_path, seed_demo=True)) as client:
        farms = client.get("/farms").json()
        assert [f["name"] for f in farms] == ["Demo Farm"]
        plots = client.get(f"/farms/{farms[0]['id']}/plots").json()
        assert len(plots) == 2 and all(p["in_demo_region"] for p in plots)
        assert plots[0]["current_crop"] == "milho"


def test_seed_demo_does_not_duplicate_on_restart(tmp_path):
    for _ in range(2):
        with TestClient(app_with(tmp_path, seed_demo=True)) as client:
            assert len(client.get("/farms").json()) == 1


def test_seed_demo_leaves_existing_data_alone(tmp_path):
    with TestClient(app_with(tmp_path)) as client:
        client.post("/farms", json={"name": "Minha roça", "municipality": "Picos", "state": "PI"})
    with TestClient(app_with(tmp_path, seed_demo=True)) as client:
        assert [f["name"] for f in client.get("/farms").json()] == ["Minha roça"]


def test_no_seed_by_default(tmp_path):
    with TestClient(app_with(tmp_path)) as client:
        assert client.get("/farms").json() == []


def test_seed_demo_reads_environment(monkeypatch):
    monkeypatch.setenv("SEED_DEMO", "1")
    assert Settings().seed_demo is True
    monkeypatch.setenv("SEED_DEMO", "0")
    assert Settings().seed_demo is False


@respx.mock
def test_read_only_cache_directory_does_not_break_live_data(tmp_path, monkeypatch):
    respx.get(URL).mock(return_value=httpx.Response(200, json=RECENT_JSON))

    def read_only(self, *args, **kwargs):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(Path, "write_text", read_only)
    monkeypatch.setattr(Path, "mkdir", read_only)
    df = PowerClient(tmp_path / "ro", live=True, today=lambda: TODAY).recent(-10.27, -37.05)
    assert not df.empty


def test_old_demo_property_is_renamed_to_english(tmp_path):
    import sqlite3

    with TestClient(app_with(tmp_path)) as client:
        farm = client.post("/farms", json={"name": "Sítio Demonstração", "municipality": "Aquidabã",
                                           "state": "SE"}).json()
        ring = [[-37.05, -10.27], [-37.04, -10.27], [-37.04, -10.26], [-37.05, -10.26],
                [-37.05, -10.27]]
        client.post(f"/farms/{farm['id']}/plots", json={
            "name": "Talhão 1", "geometry": {"type": "Polygon", "coordinates": [ring]}})
        client.post("/farms", json={"name": "Minha roça", "municipality": "Picos", "state": "PI"})
    with TestClient(app_with(tmp_path)) as client:  # restart runs the migration
        assert [f["name"] for f in client.get("/farms").json()] == ["Demo Farm", "Minha roça"]
        assert client.get("/farms/1/plots").json()[0]["name"] == "Field 1"
    assert sqlite3.connect(tmp_path / "var" / "app.db").execute(
        "SELECT owner FROM farm WHERE id = 1").fetchone() == ("Demo farmer",)
