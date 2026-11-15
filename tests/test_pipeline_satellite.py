from datetime import date

import numpy as np
import pandas as pd
import xarray as xr

from pipeline import appeears, gpm
from pipeline.region import load_bbox
from tests.helpers import FIXTURES


def test_load_bbox_reads_region_json():
    assert load_bbox(FIXTURES / "data" / "region.json") == (-37.25, -10.45, -36.85, -10.10)


def test_appeears_build_task_payload():
    task = appeears.build_task(
        "field-shift", [("MOD13Q1.061", "_250m_16_days_NDVI")],
        (-37.25, -10.45, -36.85, -10.10), date(2020, 1, 1), date(2020, 12, 31))
    assert task["task_type"] == "area" and task["task_name"] == "field-shift"
    params = task["params"]
    assert params["dates"] == [{"startDate": "01-01-2020", "endDate": "12-31-2020"}]
    assert params["layers"] == [{"product": "MOD13Q1.061", "layer": "_250m_16_days_NDVI"}]
    assert params["output"] == {"format": {"type": "netcdf4"}, "projection": "geographic"}
    ring = params["geo"]["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1] == [-37.25, -10.45] and len(ring) == 5


def test_appeears_mask_invalid_values():
    da = xr.DataArray([-3000.0, -0.5, 0.3, 1.5, 0.9], dims="x")
    masked = appeears.mask_invalid(da, valid_min=-0.2, valid_max=1.0)
    assert np.isnan(masked.values).tolist() == [True, True, False, True, False]


def test_gpm_month_chunks_cover_range_without_overlap():
    chunks = gpm.date_chunks(date(2015, 1, 1), date(2015, 12, 31), months=6)
    assert chunks == [(date(2015, 1, 1), date(2015, 6, 30)), (date(2015, 7, 1), date(2015, 12, 31))]
    short = gpm.date_chunks(date(2015, 11, 10), date(2016, 1, 20), months=2)
    assert short[0][0] == date(2015, 11, 10) and short[-1][1] == date(2016, 1, 20)
    assert all(a[1] < b[0] for a, b in zip(short, short[1:], strict=False))


def test_gpm_to_layer_reorders_dims_and_masks_fill():
    times = pd.date_range("2020-01-01", periods=2)
    data = np.array([[[1.0, 2.0, 3.0]], [[4.0, -9999.9, 6.0]]])  # (time, lon=1... ) ordem lon, lat
    ds = xr.Dataset({"precipitation": (("time", "lon", "lat"), data.reshape(2, 3, 1))},
                    coords={"time": times, "lon": [-37.2, -37.1, -37.0], "lat": [-10.3]})
    layer = gpm.to_layer(ds)
    assert layer.dims == ("time", "lat", "lon")
    assert np.isnan(layer.values).sum() == 1 and layer.isel(time=0, lat=0).values.tolist() == [
        1.0, 2.0, 3.0]


def touch(folder, day, prefix="1"):
    name = (f"{prefix}_GPM_3IMERGDF.07_3B-DAY.MS.MRG.3IMERG.{day}-S000000-E235959.V07B"
            "_precipitation_subsetted.nc4")
    (folder / name).touch()
    return folder / name


def test_downloaded_days_keeps_one_file_per_day(tmp_path):
    touch(tmp_path, "20150101", "1")
    newer = touch(tmp_path, "20150101", "2")
    touch(tmp_path, "20150102")
    (tmp_path / "notes.txt").touch()
    days = gpm.downloaded_days(tmp_path)
    assert list(days) == [date(2015, 1, 1), date(2015, 1, 2)]
    assert days[date(2015, 1, 1)] == newer  # o de nome maior (job mais recente)


def test_resume_start_is_the_day_after_the_last_contiguous_day(tmp_path):
    for day in ("20150101", "20150102", "20150103", "20150110"):
        touch(tmp_path, day)
    days = gpm.downloaded_days(tmp_path)
    assert gpm.resume_start(days, date(2015, 1, 1)) == date(2015, 1, 4)  # o buraco é refeito
    assert gpm.resume_start({}, date(2015, 1, 1)) == date(2015, 1, 1)
    assert gpm.resume_start(days, date(2015, 1, 2)) == date(2015, 1, 4)
