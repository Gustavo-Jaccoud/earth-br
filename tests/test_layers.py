import numpy as np
import pandas as pd
import pytest
import xarray as xr

from pipeline.layers import write_layer


def array(dims=("time", "lat", "lon")):
    shape = {"time": 2, "lat": 3, "lon": 4}
    coords = {"time": pd.date_range("2020-01-01", periods=2), "lat": [-10.3, -10.2, -10.1],
              "lon": [-37.2, -37.1, -37.0, -36.9]}
    return xr.DataArray(np.ones([shape[d] for d in dims]), dims=dims,
                        coords={d: coords[d] for d in dims})


def test_write_layer_contract(tmp_path):
    path = write_layer(array(), "ndvi", source="NASA MODIS", product="MOD13Q1.061",
                       units="1", resolution="250 m", out_dir=tmp_path)
    assert path == tmp_path / "ndvi.nc"
    ds = xr.open_dataset(path)
    assert list(ds.data_vars) == ["value"]
    assert ds["value"].dims == ("time", "lat", "lon")
    assert ds.attrs["source"] == "NASA MODIS" and ds.attrs["units"] == "1"
    assert ds.attrs["product"] == "MOD13Q1.061" and ds.attrs["resolution"] == "250 m"


def test_write_layer_reorders_dims(tmp_path):
    path = write_layer(array(("lat", "lon", "time")), "ndvi", source="s", product="p",
                       units="1", resolution="r", out_dir=tmp_path)
    assert xr.open_dataset(path)["value"].dims == ("time", "lat", "lon")


def test_write_layer_rejects_wrong_dims(tmp_path):
    with pytest.raises(ValueError, match="time, lat, lon"):
        write_layer(array(("time", "lat")), "ndvi", source="s", product="p", units="1",
                    resolution="r", out_dir=tmp_path)


def test_write_layer_rejects_unknown_layer(tmp_path):
    with pytest.raises(ValueError, match="camada"):
        write_layer(array(), "foo", source="s", product="p", units="1", resolution="r",
                    out_dir=tmp_path)
