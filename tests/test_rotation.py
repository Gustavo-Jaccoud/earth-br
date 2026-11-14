import pytest

from app.repositories.rasters import RasterStore
from tests.helpers import install_power, make_layer, make_plot

BODY = {"options": [["milho", "feijao"], ["sorgo", "feijao_caupi"]]}


def compare(client, plot, body=BODY):
    return client.post(f"/plots/{plot['id']}/rotation/compare", json=body)


@pytest.fixture
def plot(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    return plot


def scores(option):
    return {s["name"]: s for s in option["scores"]}


def test_compare_ranks_and_renormalizes_without_ndvi(client, plot):
    body = compare(client, plot).json()
    assert [o["rank"] for o in body["options"]] == [1, 2]
    assert body["options"][0]["total"] >= body["options"][1]["total"]
    for option in body["options"]:
        s = scores(option)
        assert s["soil"]["score"] is None and s["soil"]["source"] == "NASA MODIS"
        assert s["water"]["score"] is not None and s["water"]["source"] == "NASA POWER"
    milho = next(o for o in body["options"] if o["crops"] == ["milho", "feijao"])
    s = scores(milho)
    assert s["suitability"]["score"] == 35.5 and s["suitability"]["source"] == "FAO GAEZ v4"
    expected = (0.5 * s["water"]["score"] + 0.3 * s["suitability"]["score"]) / 0.8
    assert milho["total"] == pytest.approx(expected, abs=0.1)  # pesos renormalizados sem 'soil'


def test_crop_without_gaez_data_is_no_data_and_leaves_the_score(client, plot):
    body = compare(client, plot, {"options": [["milho"], ["palma"]]}).json()
    palma = next(o for o in body["options"] if o["crops"] == ["palma"])
    s = scores(palma)
    assert s["suitability"]["score"] is None
    assert palma["total"] == pytest.approx(s["water"]["score"], abs=0.1)  # só 'water' sobra


def test_soil_bonus_for_restoring_crop(client, tmp_path, plot):
    make_layer(tmp_path, "ndvi", "2024-01-01", "2026-11-14", value=0.3, source="NASA MODIS",
               units="1")
    client.app.state.rasters = RasterStore(tmp_path)
    body = compare(client, plot, {"options": [["milho"], ["feijao"]]}).json()
    soil = {tuple(o["crops"]): scores(o)["soil"]["score"] for o in body["options"]}
    assert soil[("milho",)] == pytest.approx(20.0)  # (0.3 - 0.2) / (0.7 - 0.2) * 100
    assert soil[("feijao",)] == pytest.approx(45.0)  # + soil_restoring_bonus (25)


def test_verdict_names_the_best_option(client, plot):
    body = compare(client, plot).json()
    best = body["options"][0]
    assert "best option" in body["verdict"]
    assert f"{best['total']:.1f}" in body["verdict"]


def test_unknown_crop_422(client, plot):
    response = compare(client, plot, {"options": [["milho"], ["arroz"]]})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "arroz" in detail and "milho" in detail


@pytest.mark.parametrize(
    "options", [[["milho"]], [["milho"], []], [["a", "b", "c", "d"], ["milho"]]]
)
def test_invalid_option_shapes_422(client, plot, options):
    assert compare(client, plot, {"options": options}).status_code == 422


def test_unknown_plot_404(client):
    assert client.post("/plots/999/rotation/compare", json=BODY).status_code == 404


def test_power_unavailable_503(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot, history=False, recent=False)
    assert compare(client, plot).status_code == 503
