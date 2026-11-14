"""Cria a propriedade de demonstração (Aquidabã/SE) pela API e aquece o cache da NASA POWER.

Uso (com a API rodando):  python -m pipeline.seed_demo
Idempotente: rodar de novo reaproveita o que já existe.
"""
import httpx

FARM = {"name": "Sítio Demonstração", "municipality": "Aquidabã", "state": "SE",
        "ibge_code": "2800209", "owner": "Produtor de demonstração"}


def _square(lon: float, lat: float, size: float = 0.002) -> dict:
    """Quadrado de ~5 ha com canto sudoeste em (lon, lat)."""
    ring = [(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size), (lon, lat)]
    return {"type": "Polygon", "coordinates": [ring]}


# Os dois talhões caem na mesma célula do POWER (~50 km), então compartilham o cache.
PLOTS = [
    {"name": "Talhão 1", "current_crop": "milho", "geometry": _square(-37.050, -10.270)},
    {"name": "Talhão 2", "current_crop": "feijao", "geometry": _square(-37.052, -10.274)},
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
    # O panorama de causas usa o clima do centro da região: aquece esse cache também.
    response = client.get("/regional/causes", params={"crop": "milho"})
    if response.status_code != 200:
        print(f"AVISO: causas ambientais indisponíveis ({response.status_code})")
    return plot_ids


if __name__ == "__main__":
    main()
