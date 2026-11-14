from datetime import date

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box

from app.repositories.rasters import RasterStore
from pipeline.layers import write_layer
from tests.helpers import install_power, make_layer, make_plot

FAR_SQUARE = [[-40.51, -9.41], [-40.50, -9.41], [-40.50, -9.40], [-40.51, -9.40], [-40.51, -9.41]]
LONS = [-37.05, -37.04, -37.03, -37.02]
LATS = [-10.30, -10.29, -10.28, -10.27]


@pytest.fixture
def store(tmp_path):
    values = np.arange(16, dtype=float).reshape(1, 4, 4) + np.array([0, 100]).reshape(2, 1, 1)
    da = xr.DataArray(values, dims=("time", "lat", "lon"),
                      coords={"time": pd.date_range("2020-01-01", periods=2),
                              "lat": LATS, "lon": LONS})
    write_layer(da, "precipitation", source="NASA TESTE", product="T", units="mm/day",
                resolution="0.01 deg", out_dir=tmp_path / "rasters")
    return RasterStore(tmp_path)


def test_has_meta_coverage(store):
    assert store.has("precipitation") and not store.has("ndvi")
    assert store.meta("precipitation") == {"units": "mm/day", "source": "NASA TESTE"}
    assert store.coverage("precipitation") == (date(2020, 1, 1), date(2020, 1, 2))
    assert store.coverage("ndvi") is None


def test_plot_series_mean_of_inside_pixels(store):
    series = store.plot_series("precipitation", box(-37.045, -10.295, -37.025, -10.275))
    assert series.tolist() == [7.5, 107.5]  # pixels 5, 6, 9, 10
    assert list(series.index) == list(pd.date_range("2020-01-01", periods=2))


def test_plot_series_small_plot_uses_nearest_pixel(store):
    series = store.plot_series("precipitation", box(-37.0399, -10.2899, -37.0398, -10.2898))
    assert series.tolist() == [5.0, 105.0]


def test_plot_series_none_outside_extent_or_missing_layer(store):
    assert store.plot_series("precipitation", box(-40.51, -9.41, -40.50, -9.40)) is None
    assert store.plot_series("ndvi", box(-37.045, -10.295, -37.025, -10.275)) is None


def test_satellite_api_returns_series(client, tmp_path):
    plot = make_plot(client)
    make_layer(tmp_path, "ndvi", "2026-10-01", "2026-10-20", value=0.4, source="NASA MODIS",
               units="1")
    client.app.state.rasters = RasterStore(tmp_path)
    body = client.get(f"/plots/{plot['id']}/satellite/ndvi?start=2026-10-05&end=2026-10-07").json()
    assert body["source"] == "NASA MODIS" and body["layer"] == "ndvi" and body["unit"] == "1"
    assert [v["value"] for v in body["values"]] == [0.4, 0.4, 0.4]


def test_satellite_outside_region_404(client, tmp_path):
    plot = make_plot(client, FAR_SQUARE)
    make_layer(tmp_path, "ndvi", "2026-10-01", "2026-10-20")
    client.app.state.rasters = RasterStore(tmp_path)
    response = client.get(f"/plots/{plot['id']}/satellite/ndvi")
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Dados de satélite disponíveis apenas para a região de demonstração (Aquidabã/SE)."
    )


def test_satellite_missing_layer_404(client):
    plot = make_plot(client)
    assert client.get(f"/plots/{plot['id']}/satellite/soil_moisture").status_code == 404


def test_satellite_unknown_layer_422(client):
    plot = make_plot(client)
    assert client.get(f"/plots/{plot['id']}/satellite/foo").status_code == 422


def test_signals_prefer_satellite_when_covered(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    make_layer(tmp_path, "precipitation", "2015-01-01", "2026-12-31", value=2.0,
               source="NASA GPM TESTE", units="mm/day")
    client.app.state.rasters = RasterStore(tmp_path)
    signals = {s["kind"]: s for s in client.get(f"/plots/{plot['id']}/signals").json()["signals"]}
    assert signals["rain"]["source"] == "NASA GPM TESTE"
    assert signals["rain"]["value"] == 60.0 and signals["rain"]["color"] == "green"
    assert signals["soil_moisture"]["source"] == "NASA POWER"  # sem raster de umidade


def test_signals_fallback_when_raster_short(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    make_layer(tmp_path, "precipitation", "2025-01-01", "2026-12-31")  # só 1 ano de histórico
    client.app.state.rasters = RasterStore(tmp_path)
    signals = client.get(f"/plots/{plot['id']}/signals").json()["signals"]
    assert signals[0]["source"] == "NASA POWER"


def test_signals_fallback_when_raster_does_not_cover_reference(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    make_layer(tmp_path, "precipitation", "2015-01-01", "2026-06-30")  # termina antes da data
    client.app.state.rasters = RasterStore(tmp_path)
    assert client.get(f"/plots/{plot['id']}/signals").json()["signals"][0]["source"] == "NASA POWER"

