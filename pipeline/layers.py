"""Contrato dos rasters que o pipeline entrega para a API (data/rasters/<layer>.nc)."""
from pathlib import Path

import xarray as xr

LAYERS = ("ndvi", "soil_moisture", "precipitation")
DIMS = ("time", "lat", "lon")


def write_layer(da: xr.DataArray, layer: str, source: str, product: str, units: str,
                resolution: str, out_dir: Path) -> Path:
    """Grava `da` como `<out_dir>/<layer>.nc`: variável `value`, dims (time, lat, lon) em graus
    WGS84, e atributos `source`, `product`, `units`, `resolution`."""
    if layer not in LAYERS:
        raise ValueError(f"camada desconhecida: {layer!r} (use {', '.join(LAYERS)})")
    if set(da.dims) != set(DIMS):
        raise ValueError(f"o raster precisa ter as dimensões time, lat, lon (veio {da.dims})")
    ds = da.transpose(*DIMS).rename("value").to_dataset()
    ds.attrs.update(source=source, product=product, units=units, resolution=resolution)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{layer}.nc"
    ds.to_netcdf(path, engine="h5netcdf")
    return path
