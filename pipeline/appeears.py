"""Baixa NDVI (MODIS MOD13Q1) e umidade do solo (SMAP SPL3SMP_E) via NASA AppEEARS.

Uso:  EARTHDATA_USERNAME=... EARTHDATA_PASSWORD=... python -m pipeline.appeears
Cria 1 tarefa de área com a bbox da região de demonstração, espera (minutos), baixa os netCDF
para data/raw/appeears/ e converte para data/rasters/{ndvi,soil_moisture}.nc.

ATENÇÃO: `build_task` e `mask_invalid` têm testes; o fluxo de rede (login → tarefa → download)
precisa de uma conta Earthdata e foi escrito pela documentação da API, sem teste ao vivo.
Camadas e faixas válidas conferidas em GET /product/<produto>.
"""
import os
import time
from datetime import date
from pathlib import Path

import httpx
import xarray as xr

from pipeline.layers import write_layer
from pipeline.region import load_bbox

API = "https://appeears.earthdatacloud.nasa.gov/api"

# camada do nosso contrato: (produto, camada no AppEEARS, mínimo válido, máximo válido,
#                            fonte, unidade, resolução)
SOURCES = {
    "ndvi": ("MOD13Q1.061", "_250m_16_days_NDVI", -0.2, 1.0, "NASA MODIS", "1", "250 m"),
    "soil_moisture": ("SPL3SMP_E.006", "Soil_Moisture_Retrieval_Data_AM_soil_moisture",
                      0.02, 0.5, "NASA SMAP", "m3/m3", "9 km"),
}


def build_task(name: str, layers: list[tuple[str, str]], bbox: tuple[float, float, float, float],
               start: date, end: date) -> dict:
    west, south, east, north = bbox
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {
        "task_type": "area",
        "task_name": name,
        "params": {
            "dates": [{"startDate": start.strftime("%m-%d-%Y"),
                       "endDate": end.strftime("%m-%d-%Y")}],
            "layers": [{"product": p, "layer": layer} for p, layer in layers],
            "geo": {"type": "FeatureCollection", "features": [{
                "type": "Feature", "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [ring]}}]},
            "output": {"format": {"type": "netcdf4"}, "projection": "geographic"},
        },
    }


def mask_invalid(da: xr.DataArray, valid_min: float, valid_max: float) -> xr.DataArray:
    """Troca por NaN o que está fora da faixa válida do produto (inclui o preenchimento)."""
    return da.where((da >= valid_min) & (da <= valid_max))


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: httpx.Client, username: str, password: str) -> str:
    response = client.post(f"{API}/login", auth=(username, password))
    response.raise_for_status()
    return response.json()["token"]


def submit(client: httpx.Client, token: str, task: dict) -> str:
    response = client.post(f"{API}/task", json=task, headers=_auth(token))
    response.raise_for_status()
    return response.json()["task_id"]


def wait(client: httpx.Client, token: str, task_id: str, poll_seconds: int = 30,
         timeout_seconds: int = 4 * 3600) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{API}/task/{task_id}", headers=_auth(token))
        response.raise_for_status()
        status = response.json().get("status")
        print(f"tarefa {task_id}: {status}")
        if status == "done":
            return
        if status in ("error", "deleted"):
            raise RuntimeError(f"A tarefa do AppEEARS terminou com status {status}.")
        time.sleep(poll_seconds)
    raise TimeoutError("A tarefa do AppEEARS não terminou a tempo.")


def download(client: httpx.Client, token: str, task_id: str, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    listing = client.get(f"{API}/bundle/{task_id}", headers=_auth(token))
    listing.raise_for_status()
    paths = []
    for item in listing.json()["files"]:
        if not item["file_name"].endswith(".nc"):
            continue
        target = out_dir / Path(item["file_name"]).name
        with client.stream("GET", f"{API}/bundle/{task_id}/{item['file_id']}",
                           headers=_auth(token), follow_redirects=True) as response:
            response.raise_for_status()
            with target.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        paths.append(target)
    return paths


def convert(files: list[Path], data_dir: Path) -> list[Path]:
    written = []
    for layer, (product, name, vmin, vmax, source, units, resolution) in SOURCES.items():
        match = next((f for f in files if product in f.name), None)
        if match is None:
            print(f"{layer}: nenhum arquivo de {product} no resultado, pulando")
            continue
        with xr.open_dataset(match) as ds:
            variable = name if name in ds.data_vars else next(
                v for v in ds.data_vars if name.lower() in v.lower())
            da = mask_invalid(ds[variable].load(), vmin, vmax)
        written.append(write_layer(da, layer, source=source, product=product, units=units,
                                   resolution=resolution, out_dir=data_dir / "rasters"))
    return written


def main(start: date = date(2015, 4, 1), end: date | None = None,
         data_dir: Path = Path("data")) -> None:
    username = os.environ.get("EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD")
    if not username or not password:
        raise SystemExit("Defina EARTHDATA_USERNAME e EARTHDATA_PASSWORD (conta gratuita em "
                         "https://urs.earthdata.nasa.gov).")
    layers = [(p, n) for p, n, *_ in SOURCES.values()]
    task = build_task("field-shift", layers, load_bbox(data_dir / "region.json"), start,
                      end or date.today())
    with httpx.Client(timeout=120) as client:
        token = login(client, username, password)
        task_id = submit(client, token, task)
        wait(client, token, task_id)
        files = download(client, token, task_id, data_dir / "raw" / "appeears")
    for path in convert(files, data_dir):
        print(f"gravado {path}")


if __name__ == "__main__":
    main()
