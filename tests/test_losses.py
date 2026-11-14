import pandas as pd
import pytest

from app.repositories.ibge import IbgeRepository
from app.services import losses
from tests.helpers import FIXTURES


def frame(crop, years, planted, production_t, yield_kg):
    return pd.DataFrame({
        "crop": crop, "year": years, "planted_ha": planted, "production": production_t,
        "production_unit": "Toneladas", "yield_kg_ha": yield_kg,
    })


def test_yearly_loss_drought_year():
    df = frame("Milho", [2010, 2011, 2012, 2013], 100.0, [200.0, 200.0, 200.0, 50.0],
               [2000.0, 2000.0, 2000.0, 500.0])
    result = losses.yearly_loss(df).set_index("year")["loss"]
    assert result[2013] == pytest.approx(0.75)  # 50 t contra 100 ha x 2000 kg/ha = 200 t
    assert result[2010] == 0.0


def test_yearly_loss_ignores_other_units_and_zero_area():
    df = frame("Abacaxi", [2010, 2011], [100.0, 0.0], [5.0, 5.0], [1000.0, 1000.0])
    df.loc[0, "production_unit"] = "Mil frutos"
    assert losses.yearly_loss(df).empty


def test_ranking_order_and_filters():
    ok = frame("Milho", range(2010, 2016), 1000.0, [1000, 1000, 1000, 500, 1000, 1000],
               [1000.0] * 6)
    mild = frame("Feijão", range(2010, 2016), 1000.0, [1000, 1000, 1000, 900, 1000, 1000],
                 [1000.0] * 6)
    short = frame("Soja", range(2010, 2013), 1000.0, [100, 100, 100], [1000.0] * 3)
    small = frame("Fava", range(2010, 2016), 5.0, [5] * 6, [1000.0] * 6)
    items = losses.ranking(pd.concat([ok, mild, short, small]), min_years=5,
                           min_mean_planted_ha=100)
    assert [i.crop for i in items] == ["Milho", "Feijão"]
    assert items[0].worst_year == 2013 and items[0].worst_loss_pct == 50.0
    assert items[0].mean_loss_pct == pytest.approx(8.3, abs=0.1) and items[0].years == 6


def test_crop_loss_pct_falls_back_to_state():
    repo = IbgeRepository(FIXTURES / "data")
    pct, level = losses.crop_loss_pct(repo, "Milho (em grão)", "2800209", "28")
    assert level == "municipality" and pct > 0
    pct, level = losses.crop_loss_pct(repo, "Milho (em grão)", "9999999", "28")
    assert level == "state"
    assert losses.crop_loss_pct(repo, "Palma", "2800209", "28") is None
    assert losses.crop_loss_pct(repo, "Abacaxi*", "2800209", "28") is None  # só 3 anos


def test_repository_rows_and_names():
    repo = IbgeRepository(FIXTURES / "data")
    assert repo.territory_name("region", "2") == "Nordeste"
    assert repo.territory_name("municipality", "2800209") == "Aquidabã (SE)"
    assert repo.territory_name("state", "99") is None
    assert repo.rows("state", "28")["territory_code"].unique().tolist() == ["28"]
    assert repo.rows("state", "99").empty


def test_repository_without_file_is_empty(tmp_path):
    repo = IbgeRepository(tmp_path)
    assert repo.rows("region", "2").empty and repo.territory_name("region", "2") is None


def test_losses_api_region(client):
    body = client.get("/regional/losses").json()
    assert body["level"] == "region" and body["territory_name"] == "Nordeste"
    assert body["source"] == "IBGE PAM" and body["period"] == [2012, 2017]
    crops = [i["crop"] for i in body["items"]]
    assert crops[0] == "Milho (em grão)" and "Abacaxi*" not in crops
    pcts = [i["mean_loss_pct"] for i in body["items"]]
    assert pcts == sorted(pcts, reverse=True)


def test_losses_api_state_and_municipality(client):
    assert client.get("/regional/losses?level=state&code=28").json()["territory_name"] == "Sergipe"
    body = client.get("/regional/losses?level=municipality&code=2800209").json()
    assert body["territory_name"] == "Aquidabã (SE)" and body["items"]


def test_losses_api_unknown_territory_404(client):
    assert client.get("/regional/losses?level=state&code=99").status_code == 404


def test_losses_api_invalid_level_422(client):
    assert client.get("/regional/losses?level=pais&code=1").status_code == 422
