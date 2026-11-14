import shutil
from datetime import date
from pathlib import Path

from app.clients.power import PowerClient

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 14)
LAST_VALID_DAY = date(2026, 11, 11)  # último dia sem -999 em power_recent.json

SQUARE = [[-37.05, -10.27], [-37.04, -10.27], [-37.04, -10.26], [-37.05, -10.26], [-37.05, -10.27]]


def make_plot(client, ring=None) -> dict:
    farm = client.post(
        "/farms", json={"name": "Sítio", "municipality": "Aquidabã", "state": "SE"}
    ).json()
    body = {"name": "Talhão 1", "geometry": {"type": "Polygon", "coordinates": [ring or SQUARE]}}
    return client.post(f"/farms/{farm['id']}/plots", json=body).json()


def install_power(client, tmp_path, plot, *, history=True, recent=True, live=False, http=None):
    """Põe na app um PowerClient cujo cache tem as fixtures reais para o centroide do talhão."""
    power = PowerClient(tmp_path / "power_cache", live=live, http=http, today=lambda: TODAY)
    lon, lat = plot["centroid"]
    for kind, enabled in (("history", history), ("recent", recent)):
        if enabled:
            path = power.cache_path(kind, lat, lon)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(FIXTURES / f"power_{kind}.json", path)
    client.app.state.power = power
    return power
