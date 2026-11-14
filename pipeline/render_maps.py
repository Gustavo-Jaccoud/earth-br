"""Gera as camadas de mapa (PNG + limites) a partir dos rasters de data/rasters/.

Uso:  python -m pipeline.render_maps
Saída: data/maps/<camada>/index.json e um PNG por mês (RGBA, sem dado = transparente), prontos
para o frontend sobrepor como imagem (Leaflet/MapLibre) usando os limites de `bounds`.
"""
import json
import math
from pathlib import Path
from typing import Literal

import matplotlib
import numpy as np
import xarray as xr
from matplotlib.colors import to_hex

# Os rasters de satélite são grosseiros: repete pixels para a imagem não ficar minúscula.
MIN_SIDE_PX = 256

# camada: (paleta, mínimo, máximo, agregação mensal, unidade do mapa)
LAYERS = {
    "ndvi": ("RdYlGn", 0.0, 0.8, "mean", None),
    "soil_moisture": ("YlGnBu", 0.0, 0.5, "mean", None),
    "precipitation": ("Blues", 0.0, 300.0, "sum", "mm/month"),
}


def monthly(da: xr.DataArray, agg: Literal["sum", "mean"]) -> xr.DataArray:
    grouped = da.resample(time="MS")
    return grouped.sum(min_count=1) if agg == "sum" else grouped.mean()


def _pixel_step(values: np.ndarray) -> float:
    return float(abs(np.diff(values)).mean()) if len(values) > 1 else 0.0


def render_layer(nc_path: Path, out_dir: Path, cmap: str, vmin: float, vmax: float,
                 months: int = 24, agg: Literal["sum", "mean"] = "mean",
                 unit: str | None = None) -> dict:
    nc_path, out_dir = Path(nc_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with xr.open_dataset(nc_path, engine="h5netcdf") as ds:
        value = ds["value"].load()
        units = unit or ds.attrs.get("units", "")
    series = monthly(value, agg).isel(time=slice(-months, None))
    series = series.sortby("lat", ascending=False).sortby("lon")  # norte em cima, oeste à esquerda

    lat, lon = value["lat"].values, value["lon"].values
    half_y, half_x = _pixel_step(lat) / 2, _pixel_step(lon) / 2
    bounds = [[round(float(lat.min() - half_y), 6), round(float(lon.min() - half_x), 6)],
              [round(float(lat.max() + half_y), 6), round(float(lon.max() + half_x), 6)]]

    colormap = matplotlib.colormaps[cmap]
    periods = []
    for t in series["time"].values:
        period = str(t)[:7]
        arr = series.sel(time=t).values
        rgba = colormap(np.clip((arr - vmin) / (vmax - vmin), 0, 1))
        rgba[np.isnan(arr), 3] = 0.0
        scale = max(1, math.ceil(MIN_SIDE_PX / max(arr.shape)))
        rgba = np.repeat(np.repeat(rgba, scale, axis=0), scale, axis=1)
        matplotlib.image.imsave(out_dir / f"{period}.png", rgba)
        periods.append({"period": period, "file": f"{period}.png", "bounds": bounds})

    legend = [{"color": to_hex(colormap(i / 4)), "label": f"{v:g}"}
              for i, v in enumerate(np.linspace(vmin, vmax, 5))]
    index = {"layer": nc_path.stem, "unit": units, "legend": legend, "periods": periods}
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    return index


def main(data_dir: Path = Path("data")) -> None:
    for layer, (cmap, vmin, vmax, agg, unit) in LAYERS.items():
        nc = data_dir / "rasters" / f"{layer}.nc"
        if not nc.exists():
            print(f"{layer}: raster não encontrado ({nc}), pulando")
            continue
        index = render_layer(nc, data_dir / "maps" / layer, cmap, vmin, vmax, agg=agg, unit=unit)
        print(f"{layer}: {len(index['periods'])} meses em {data_dir / 'maps' / layer}")


if __name__ == "__main__":
    main()
