from pathlib import Path

import numpy as np
import xarray as xr

SOURCE = "FAO GAEZ v4"
PERIOD = "1981-2010"


class GaezRepository:
    """Lê data/gaez/gaez.nc (gerado por pipeline.gaez): aptidão e rendimento por cultura."""

    def __init__(self, data_dir: Path):
        path = Path(data_dir) / "gaez" / "gaez.nc"
        self.ds = None
        if path.exists():
            with xr.open_dataset(path, engine="h5netcdf") as ds:
                self.ds = ds.load()

    def at(self, gaez_name: str | None, lat: float, lon: float) -> tuple[float, float] | None:
        """(aptidão 0..100, rendimento atingível kg/ha) na célula do ponto; None sem dado."""
        ds = self.ds
        if ds is None or gaez_name is None or gaez_name not in ds["crop"].values:
            return None
        half = abs(float(ds["lat"][1] - ds["lat"][0])) / 2 if ds.sizes["lat"] > 1 else 0.05
        if not (float(ds["lat"].min()) - half <= lat <= float(ds["lat"].max()) + half
                and float(ds["lon"].min()) - half <= lon <= float(ds["lon"].max()) + half):
            return None
        cell = ds.sel(crop=gaez_name).sel(lat=lat, lon=lon, method="nearest")
        suitability, yield_kg = float(cell["suitability"]), float(cell["yield_kg_ha"])
        if np.isnan(suitability) or np.isnan(yield_kg):
            return None
        return round(suitability, 1), round(yield_kg, 1)
