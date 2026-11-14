import pandas as pd
import pytest

from app.repositories.ibge import IbgeRepository
from app.repositories.region import load_region
from app.services import causes
from app.services.texts import render
from tests.helpers import FIXTURES, install_power

REGION_CENTER = {"centroid": (-37.05, -10.275)}  # centro da bbox da região de demo


def history(drought_year=2012):
    index = pd.date_range("2001-01-01", "2020-12-31")
    rain = [0.5 if d.year == drought_year else 1.0 for d in index]
    return pd.DataFrame({"PRECTOTCORR": rain}, index=index)


def loss_frame(losses_by_year):
    return pd.DataFrame({"crop": "Milho", "year": list(losses_by_year),
                         "planted_ha": 100.0, "loss": list(losses_by_year.values())})


def test_season_anomaly_sign():
    anomaly = causes.season_rain_anomaly(history(2012), [4, 5, 6, 7, 8])
    assert anomaly[2012] == pytest.approx(-48.7, abs=0.1)  # 0.5 contra média de 0.975
    assert anomaly[2013] == pytest.approx(2.6, abs=0.1)
    assert set(anomaly) == set(range(2001, 2021))


def test_build_causes_mentions_worst_drought_year():
    response = causes.build_causes(
        loss_frame({2012: 0.6, 2013: 0.5, 2014: 0.0}), {2012: -50.0, 2013: -5.0, 2014: 10.0},
        crop_name="Milho", territory_name="Aquidabã (SE)")
    assert "2012" in response.message and "60%" in response.message
    assert "2013" not in response.message  # chuva normal: perda sem causa climática clara
    assert [y.year for y in response.years] == [2012, 2013, 2014]
    assert response.years[0].loss_pct == 60.0 and response.years[0].rain_anomaly_pct == -50.0


def test_build_causes_without_drought_years():
    response = causes.build_causes(loss_frame({2012: 0.6}), {2012: -5.0}, crop_name="Milho",
                                   territory_name="X")
    assert response.message == render("causes.none")


def test_build_causes_year_without_climate_data():
    response = causes.build_causes(loss_frame({2024: 0.6}), {}, crop_name="Milho",
                                   territory_name="X")
    assert response.years[0].rain_anomaly_pct is None


def test_loss_years_fall_back_to_state(tmp_path):
    rows = []
    for level, code, years in (("municipality", "2800209", 2), ("state", "28", 6)):
        for i in range(years):
            rows.append([level, code, f"T{code}", "Milho (em grão)", 2012 + i, 100, 100, 100,
                         "Toneladas", 1000 - 100 * i])
    columns = ["level", "territory_code", "territory_name", "crop", "year", "planted_ha",
               "harvested_ha", "production", "production_unit", "yield_kg_ha"]
    (tmp_path / "ibge").mkdir()
    pd.DataFrame(rows, columns=columns).to_csv(tmp_path / "ibge" / "pam.csv", index=False)
    region = load_region(FIXTURES / "data")
    _, name = causes.loss_years(IbgeRepository(tmp_path), "Milho (em grão)", region)
    assert name == "T28"


def test_loss_years_without_data_raises():
    region = load_region(FIXTURES / "data")
    with pytest.raises(causes.NoLossData):
        causes.loss_years(IbgeRepository(FIXTURES / "data"), "Palma", region)


def test_causes_api_structure(client, tmp_path):
    install_power(client, tmp_path, REGION_CENTER)
    response = client.get("/regional/causes?crop=milho")
    assert response.status_code == 200
    body = response.json()
    assert body["territory_name"] == "Aquidabã (SE)" and body["crop"] == "milho"
    years = [y["year"] for y in body["years"]]
    assert years == sorted(years) and years[0] == 2012
    assert all(isinstance(y["rain_anomaly_pct"], float) for y in body["years"])
    assert body["message"]


def test_causes_default_crop_is_milho(client, tmp_path):
    install_power(client, tmp_path, REGION_CENTER)
    assert client.get("/regional/causes").json()["crop"] == "milho"


def test_causes_crop_without_ibge_422(client):
    response = client.get("/regional/causes?crop=palma")
    assert response.status_code == 422 and "IBGE" in response.json()["detail"]


def test_causes_unknown_crop_422(client):
    assert client.get("/regional/causes?crop=arroz").status_code == 422


def test_causes_503_when_power_unavailable(client, tmp_path):
    install_power(client, tmp_path, REGION_CENTER, history=False, recent=False)
    assert client.get("/regional/causes?crop=milho").status_code == 503
