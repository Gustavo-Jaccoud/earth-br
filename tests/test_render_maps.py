import json

import matplotlib.image as mpimg
import numpy as np
import pandas as pd
import xarray as xr

from pipeline.layers import write_layer
from pipeline.render_maps import monthly, render_layer

LATS, LONS = [-10.4, -10.3], [-37.2, -37.1]


def write(tmp_path, layer="ndvi", start="2020-01-01", end="2020-03-31", values=None, units="1"):
    times = pd.date_range(start, end)
    grid = np.array([[0.0, 0.8], [0.4, np.nan]]) if values is None else values
    data = np.broadcast_to(grid, (len(times), 2, 2)).copy()
    da = xr.DataArray(data, dims=("time", "lat", "lon"),
                      coords={"time": times, "lat": LATS, "lon": LONS})
    return write_layer(da, layer, source="NASA TESTE", product="T", units=units,
                       resolution="0.1 deg", out_dir=tmp_path / "rasters")


def test_monthly_sum_and_mean():
    index = pd.date_range("2020-01-01", "2020-02-29")
    da = xr.DataArray(np.ones((len(index), 1, 1)), dims=("time", "lat", "lon"),
                      coords={"time": index, "lat": [0.0], "lon": [0.0]})
    assert monthly(da, "sum").isel(time=0).item() == 31.0
    assert monthly(da, "mean").isel(time=1).item() == 1.0
    assert [pd.Timestamp(t).month for t in monthly(da, "sum")["time"].values] == [1, 2]


def test_render_layer_writes_index_and_pngs(tmp_path):
    nc = write(tmp_path)
    out = tmp_path / "maps" / "ndvi"
    index = render_layer(nc, out, cmap="RdYlGn", vmin=0.0, vmax=0.8)
    assert json.loads((out / "index.json").read_text()) == index
    assert [p["period"] for p in index["periods"]] == ["2020-01", "2020-02", "2020-03"]
    assert index["layer"] == "ndvi" and index["unit"] == "1" and len(index["legend"]) == 5
    assert all(set(i) == {"color", "label"} for i in index["legend"])
    # limites = bordas dos pixels (centro ± meio passo de 0,1°)
    assert index["periods"][0]["bounds"] == [[-10.45, -37.25], [-10.25, -37.05]]
    image = mpimg.imread(out / index["periods"][0]["file"])
    assert image.shape[2] == 4
    h, w = image.shape[:2]
    assert image[0, w - 1, 3] == 0  # topo-direita = lat -10.3, lon -37.1 = NaN → transparente
    assert image[0, 0, 3] == 1.0 and image[h - 1, w - 1, 3] == 1.0


def test_render_layer_limits_months(tmp_path):
    nc = write(tmp_path, start="2018-01-01", end="2020-06-30")  # 30 meses
    index = render_layer(nc, tmp_path / "maps" / "ndvi", cmap="RdYlGn", vmin=0, vmax=0.8,
                         months=24)
    assert len(index["periods"]) == 24
    assert index["periods"][-1]["period"] == "2020-06"
    assert index["periods"][0]["period"] == "2018-07"


def test_render_layer_precipitation_sums_to_mm_per_month(tmp_path):
    values = np.full((2, 2), 1.0)
    nc = write(tmp_path, layer="precipitation", start="2020-01-01", end="2020-01-31",
               values=values, units="mm/day")
    index = render_layer(nc, tmp_path / "maps" / "precipitation", cmap="Blues", vmin=0, vmax=300,
                         agg="sum", unit="mm/month")
    assert index["unit"] == "mm/month"
    assert index["legend"][-1]["label"] == "300"


def test_maps_api_urls_resolve(tmp_path, settings):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.settings import Settings

    (tmp_path / "region.json").write_text((settings.data_dir / "region.json").read_text())
    render_layer(write(tmp_path), tmp_path / "maps" / "ndvi", cmap="RdYlGn", vmin=0, vmax=0.8)
    app = create_app(Settings(data_dir=tmp_path, var_dir=tmp_path / "var", power_live=False))
    with TestClient(app) as client:
        body = client.get("/maps/ndvi").json()
        assert body["layer"] == "ndvi" and len(body["periods"]) == 3
        first = body["periods"][0]
        assert first["url"] == "/static/maps/ndvi/2020-01.png"
        image = client.get(first["url"])
        assert image.status_code == 200 and image.headers["content-type"] == "image/png"
        assert client.get("/maps/precipitation").status_code == 404


