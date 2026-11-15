"""Cria a propriedade de demonstração (Aquidabã/SE) pela API e aquece o cache da NASA POWER.

Uso (com a API rodando):  python -m pipeline.seed_demo
Idempotente: rodar de novo reaproveita o que já existe.
"""
from pathlib import Path

import httpx

from app.clients.power import GRID_LAT, GRID_LON, PowerClient, PowerUnavailable, grid_cell
from pipeline.region import load_bbox

FARM = {"name": "Demo Farm", "municipality": "Aquidabã", "state": "SE",
        "ibge_code": "2800209", "owner": "Demo farmer"}


def _square(lon: float, lat: float, size: float = 0.002) -> dict:
    """Quadrado de ~5 ha com canto sudoeste em (lon, lat)."""
    ring = [(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size), (lon, lat)]
    return {"type": "Polygon", "coordinates": [ring]}


# Os dois talhões caem na mesma célula do POWER (~50 km), então compartilham o cache.
PLOTS = [
    {"name": "Field 1", "current_crop": "milho", "geometry": _square(-37.050, -10.270)},
    {"name": "Field 2", "current_crop": "feijao", "geometry": _square(-37.052, -10.274)},
]


def _get_or_create_farm(client: httpx.Client) -> dict:
    for farm in client.get("/farms").json():
        if farm["name"] == FARM["name"]:
            return farm
    response = client.post("/farms", json=FARM)
    response.raise_for_status()
    return response.json()


def _get_or_create_plot(client: httpx.Client, farm_id: int, body: dict) -> dict:
    for plot in client.get(f"/farms/{farm_id}/plots").json():
        if plot["name"] == body["name"]:
            return plot
    response = client.post(f"/farms/{farm_id}/plots", json=body)
    response.raise_for_status()
    return response.json()


def region_cells(bbox: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """Centros de todas as células da grade do POWER que tocam a bbox da região."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lat0, lon0 = grid_cell(min_lat, min_lon)
    lat1, lon1 = grid_cell(max_lat, max_lon)
    n_lat, n_lon = round((lat1 - lat0) / GRID_LAT), round((lon1 - lon0) / GRID_LON)
    return [(lat0 + i * GRID_LAT, lon0 + j * GRID_LON)
            for i in range(n_lat + 1) for j in range(n_lon + 1)]


def warm_power_cache(data_dir: Path = Path("data"), cache_dir: Path | None = None) -> None:
    """Baixa o clima (histórico + recente) de todas as células da região para data/cache/power,
    para qualquer talhão desenhado na região funcionar sem internet."""
    client = PowerClient(cache_dir or Path(data_dir) / "cache" / "power", live=True)
    for lat, lon in region_cells(load_bbox(Path(data_dir) / "region.json")):
        try:
            client.history(lat, lon)
            client.recent(lat, lon)
            print(f"POWER célula ({lat}, {lon}): em cache")
        except PowerUnavailable:
            print(f"AVISO: não foi possível baixar a célula ({lat}, {lon}) do POWER")


def main(api_base: str = "http://localhost:8000", client: httpx.Client | None = None) -> list[int]:
    client = client or httpx.Client(base_url=api_base, timeout=120)
    farm = _get_or_create_farm(client)
    plot_ids = []
    for body in PLOTS:
        plot = _get_or_create_plot(client, farm["id"], body)
        plot_ids.append(plot["id"])
        # Consultar os semáforos faz a API baixar e guardar os dados do POWER (cache em data/).
        response = client.get(f"/plots/{plot['id']}/signals")
        status = "dados da NASA em cache" if response.status_code == 200 else (
            f"AVISO: semáforos indisponíveis ({response.status_code}): {response.text[:120]}")
        print(f"{plot['name']} (id {plot['id']}, {plot['area_ha']:.1f} ha): {status}")
    return plot_ids


if __name__ == "__main__":
    main()
    warm_power_cache()
