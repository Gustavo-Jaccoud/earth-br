import numpy as np
import pytest

from app.repositories.gaez import GaezRepository
from pipeline import gaez
from tests.helpers import FIXTURES, install_power, make_plot

OUTSIDE = [[-45.01, -5.01], [-45.0, -5.01], [-45.0, -5.0], [-45.01, -5.0], [-45.01, -5.01]]


def test_clip_cuts_global_grid_to_bbox_and_masks_nodata():
    grid = np.arange(2160 * 4320, dtype=np.int32).reshape(2160, 4320)
    grid[1200, 1700] = -9
    values, lats, lons = gaez.clip(grid, (-38.5, -10.5, -38.0, -10.0), nodata=-9)
    assert values.shape == (6, 6)
    assert lats[0] == pytest.approx(-10.0 - 1 / 24) and lons[0] == pytest.approx(-38.5 + 1 / 24)
    assert lats[0] > lats[-1]  # norte primeiro, como no raster
    assert np.isnan(values).sum() == 1


def test_build_dataset_scales_suitability_to_percent(tmp_path):
    lats, lons = np.array([-10.0, -10.1]), np.array([-37.1, -37.0])
    layers = {"Maize": (np.full((2, 2), 3590.0), np.full((2, 2), 2544.0))}
    path = gaez.write_dataset(layers, lats, lons, tmp_path)
    repo = GaezRepository(tmp_path)
    assert path == tmp_path / "gaez" / "gaez.nc"
    assert repo.at("Maize", -10.02, -37.08) == (35.9, 2544.0)


def test_repository_lookup():
    repo = GaezRepository(FIXTURES / "data")
    assert repo.at("Sorghum", -10.27, -37.05) == (46.0, 1500.0)
    assert repo.at("Sorghum", -5.0, -45.0) is None  # fora da área baixada
    assert repo.at("Opuntia", -10.27, -37.05) is None  # cultura que o GAEZ não tem


def test_repository_without_file(tmp_path):
    assert GaezRepository(tmp_path).at("Maize", -10.27, -37.05) is None


def test_suitability_endpoint_ranks_crops(client):
    plot = make_plot(client)
    body = client.get(f"/plots/{plot['id']}/suitability").json()
    assert body["source"] == "FAO GAEZ v4" and body["period"] == "1981-2010"
    assert [i["crop"] for i in body["items"]] == ["sorgo", "mandioca", "milho", "feijao",
                                                  "feijao_caupi"]
    assert body["items"][0] == {"crop": "sorgo", "name": "Sorgo", "suitability": 46.0,
                                "attainable_yield_kg_ha": 1500.0}
    assert body["without_data"] == ["palma"]


def test_suitability_endpoint_outside_downloaded_area(client):
    plot = make_plot(client, OUTSIDE)
    body = client.get(f"/plots/{plot['id']}/suitability").json()
    assert body["items"] == [] and len(body["without_data"]) == 6


def test_dry_years_endpoint(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    body = client.get(f"/plots/{plot['id']}/dry-years").json()
    assert body["source"] == "NASA POWER" and len(body["rainy_season_months"]) == 5
    years = [y["year"] for y in body["years"]]
    assert years == sorted(years) and years[0] == 2001 and years[-1] == 2023
    driest = min(body["years"], key=lambda y: y["rain_anomaly_pct"])
    assert driest["rain_anomaly_pct"] < -20 and str(driest["year"]) in body["message"]


def test_dry_years_503_without_power(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot, history=False, recent=False)
    assert client.get(f"/plots/{plot['id']}/dry-years").status_code == 503
