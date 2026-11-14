from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
import xarray as xr
from shapely.geometry import Polygon


class RasterStore:
    """Lê os rasters de satélite preparados pelo pipeline (data/rasters/<layer>.nc)."""

    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir) / "rasters"
        self._cache: dict[str, xr.Dataset] = {}

    def _path(self, layer: str) -> Path:
        return self.dir / f"{layer}.nc"

    def has(self, layer: str) -> bool:
        return self._path(layer).exists()

    def _open(self, layer: str) -> xr.Dataset | None:
        if not self.has(layer):
            return None
        if layer not in self._cache:
            with xr.open_dataset(self._path(layer), engine="h5netcdf") as ds:
                self._cache[layer] = ds.load()
        return self._cache[layer]

    def meta(self, layer: str) -> dict:
        ds = self._open(layer)
        return {"units": ds.attrs["units"], "source": ds.attrs["source"]}

    def coverage(self, layer: str) -> tuple[date, date] | None:
        ds = self._open(layer)
        if ds is None:
            return None
        times = pd.DatetimeIndex(ds["time"].values)
        return (times.min().date(), times.max().date())

    def plot_series(self, layer: str, polygon: Polygon) -> pd.Series | None:
        """Média dos pixels com centro dentro do polígono, ao longo do tempo.

        Sem pixel dentro (talhão pequeno), usa o pixel mais próximo do centroide.
        None se a camada não existe ou o talhão está fora da extensão do raster.
        """
        ds = self._open(layer)
        if ds is None:
            return None
        lon, lat = ds["lon"].values, ds["lat"].values
        c = polygon.centroid
        half_x = abs(np.diff(lon)).mean() / 2 if len(lon) > 1 else 0.0
        half_y = abs(np.diff(lat)).mean() / 2 if len(lat) > 1 else 0.0
        if not (lon.min() - half_x <= c.x <= lon.max() + half_x
                and lat.min() - half_y <= c.y <= lat.max() + half_y):
            return None
        grid_lon, grid_lat = np.meshgrid(lon, lat)
        inside = shapely.contains_xy(polygon, grid_lon, grid_lat)
        value = ds["value"]
        if inside.any():
            mask = xr.DataArray(inside, dims=("lat", "lon"), coords={"lat": lat, "lon": lon})
            series = value.where(mask).mean(dim=("lat", "lon"), skipna=True)
        else:
            series = value.sel(lat=c.y, lon=c.x, method="nearest")
        return pd.Series(series.values, index=pd.DatetimeIndex(ds["time"].values), name=layer)
