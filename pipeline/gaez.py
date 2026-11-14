"""Baixa aptidão e rendimento atingível por cultura do FAO GAEZ v4 e grava data/gaez/gaez.nc.

Uso:  python -m pipeline.gaez
Fonte: catálogo aberto do GAEZ (sem login). Cenário: clima 1981-2010, sequeiro, baixo uso de
insumos (agricultura familiar). Recorta o Nordeste do raster global (5 minutos de arco, ~9 km).
"""
from pathlib import Path

import httpx
import numpy as np
import xarray as xr
from PIL import Image

CATALOG = "https://gaez-services.fao.org/server/rest/services/res05/ImageServer/query"
CROPS = ["Maize", "Phaseolus bean", "Cowpea", "Sorghum", "Cassava"]
PERIOD = "1981-2010"
SUITABILITY = "Suitability index  range (0 – 10000); all land in grid cell"
YIELD = "Average attainable yield of best occurring suitability class in grid cell"
NORDESTE_BBOX = (-48.8, -18.4, -34.7, -1.0)  # min_lon, min_lat, max_lon, max_lat
CELL = 1 / 12  # grade global: origem (-180, 90), 4320 x 2160
NODATA = -9
Image.MAX_IMAGE_PIXELS = None  # os rasters globais passam do limite padrão do Pillow


def clip(grid: np.ndarray, bbox: tuple[float, float, float, float], nodata: float = NODATA
         ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Recorta o raster global na bbox. Devolve (valores com NaN, lats dos centros, lons)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    row0, row1 = round((90 - max_lat) / CELL), round((90 - min_lat) / CELL)
    col0, col1 = round((min_lon + 180) / CELL), round((max_lon + 180) / CELL)
    values = grid[row0:row1, col0:col1].astype("float32")
    values[values == nodata] = np.nan
    lats = 90 - (np.arange(row0, row1) + 0.5) * CELL
    lons = -180 + (np.arange(col0, col1) + 0.5) * CELL
    return values, lats, lons


def write_dataset(layers: dict[str, tuple[np.ndarray, np.ndarray]], lats: np.ndarray,
                  lons: np.ndarray, data_dir: Path) -> Path:
    """layers: cultura -> (índice de aptidão 0..10000, rendimento kg/ha). Grava
    data_dir/gaez/gaez.nc com `suitability` (0..100) e `yield_kg_ha`, dims (crop, lat, lon)."""
    crops = list(layers)
    coords = {"crop": crops, "lat": lats, "lon": lons}
    dims = ("crop", "lat", "lon")
    ds = xr.Dataset({
        "suitability": (dims, np.stack([layers[c][0] for c in crops]) / 100),
        "yield_kg_ha": (dims, np.stack([layers[c][1] for c in crops])),
    }, coords=coords)
    ds.attrs.update(source="FAO GAEZ v4", period=PERIOD, scenario="rainfed, low input",
                    resolution="5 arc-min (~9 km)", yield_units="kg dry weight / ha")
    out = Path(data_dir) / "gaez"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "gaez.nc"
    ds.to_netcdf(path, engine="h5netcdf")
    return path


def catalog_urls(client: httpx.Client) -> dict[tuple[str, str], str]:
    """(cultura, variável) -> URL de download, para o cenário escolhido."""
    crops = ",".join(f"'{c}'" for c in CROPS)
    where = (f"year='{PERIOD}' AND water_supply='Rainfed' AND input_level='Low' "
             f"AND crop IN ({crops})")
    response = client.get(CATALOG, params={
        "where": where, "outFields": "crop,variable,download_url", "returnGeometry": "false",
        "f": "json"})
    response.raise_for_status()
    rows = [f["attributes"] for f in response.json()["features"]]
    return {(r["crop"], r["variable"]): r["download_url"] for r in rows
            if r["variable"] in (SUITABILITY, YIELD)}


def _download(client: httpx.Client, url: str, raw_dir: Path) -> np.ndarray:
    path = raw_dir / url.rsplit("/", 1)[-1]
    if not path.exists():
        response = client.get(url)
        response.raise_for_status()
        path.write_bytes(response.content)
    return np.asarray(Image.open(path))


def main(data_dir: Path = Path("data"), bbox: tuple = NORDESTE_BBOX) -> Path:
    raw_dir = Path(data_dir) / "raw" / "gaez"
    raw_dir.mkdir(parents=True, exist_ok=True)
    layers = {}
    with httpx.Client(timeout=300) as client:
        urls = catalog_urls(client)
        for crop in CROPS:
            suit, lats, lons = clip(_download(client, urls[(crop, SUITABILITY)], raw_dir), bbox)
            yld, _, _ = clip(_download(client, urls[(crop, YIELD)], raw_dir), bbox)
            layers[crop] = (suit, yld)
            print(f"{crop}: recortado ({suit.shape[0]} x {suit.shape[1]} células)")
    path = write_dataset(layers, lats, lons, data_dir)
    print(f"gravado {path}")
    return path


if __name__ == "__main__":
    main()
