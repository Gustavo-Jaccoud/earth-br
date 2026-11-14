import pytest

from tests.helpers import install_power, make_plot

FAR_SQUARE = [[-40.51, -9.41], [-40.50, -9.41], [-40.50, -9.40], [-40.51, -9.40], [-40.51, -9.41]]
REGION_CENTER = {"centroid": (-37.05, -10.275)}
UNAVAILABLE = "Dado indisponível no momento."


@pytest.fixture
def plot(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    install_power(client, tmp_path, REGION_CENTER)  # cache do centro da região (causas)
    return plot


def analyze(client, plot, body=None):
    return client.post(f"/plots/{plot['id']}/reports/analysis", json=body)


def titles(report):
    return [s["title"] for s in report["sections"]]


def test_analysis_report_saved_and_listed(client, plot):
    response = analyze(client, plot)
    assert response.status_code == 201
    report = response.json()
    assert report["kind"] == "analysis" and report["plot_id"] == plot["id"]
    assert report["title"] == "Análise do Talhão 1"
    assert titles(report) == ["Condição atual", "Perdas na região", "Causas ambientais"]
    condition = report["sections"][0]
    assert "Choveu" in condition["text"] and len(condition["data"]["signals"]) == 2
    losses = report["sections"][1]["text"]
    assert "Sergipe" in losses and "Milho" in losses
    assert client.get(f"/reports/{report['id']}").json() == report
    summaries = client.get("/reports").json()
    assert summaries == [{k: report[k] for k in ("id", "plot_id", "kind", "title", "created_at")}]
    assert client.get("/reports?plot_id=999").json() == []


def test_analysis_with_rotation_and_reference_date(client, plot):
    body = {"reference_date": "2022-06-30",
            "rotation": {"options": [["milho", "feijao"], ["sorgo", "feijao_caupi"]]}}
    report = analyze(client, plot, body).json()
    assert titles(report) == ["Condição atual", "Comparação de rotação", "Perdas na região",
                              "Causas ambientais"]
    assert report["sections"][0]["data"]["reference_date"] == "2022-06-30"
    rotation = report["sections"][1]
    assert "melhor opção" in rotation["text"] and len(rotation["data"]["options"]) == 2


def test_report_survives_power_outage(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot, history=False, recent=False)
    body = {"rotation": {"options": [["milho"], ["feijao"]]}}
    response = analyze(client, plot, body)
    assert response.status_code == 201
    sections = {s["title"]: s for s in response.json()["sections"]}
    assert sections["Condição atual"]["text"] == UNAVAILABLE
    assert sections["Comparação de rotação"]["text"] == UNAVAILABLE
    assert sections["Causas ambientais"]["text"] == UNAVAILABLE
    assert sections["Perdas na região"]["text"] != UNAVAILABLE  # IBGE não depende do POWER


def test_plot_outside_region_has_no_causes_section(client, tmp_path):
    plot = make_plot(client, FAR_SQUARE)
    install_power(client, tmp_path, plot)
    report = analyze(client, plot).json()
    assert titles(report) == ["Condição atual", "Perdas na região"]


def test_reports_listed_most_recent_first(client, plot):
    first = analyze(client, plot).json()["id"]
    second = analyze(client, plot).json()["id"]
    assert [r["id"] for r in client.get(f"/reports?plot_id={plot['id']}").json()] == [second, first]


def test_unknown_crop_422_and_nothing_saved(client, plot):
    response = analyze(client, plot, {"rotation": {"options": [["milho"], ["arroz"]]}})
    assert response.status_code == 422 and "arroz" in response.json()["detail"]
    assert client.get("/reports").json() == []


def test_unknown_plot_404(client):
    assert client.post("/plots/999/reports/analysis").status_code == 404


def test_unknown_report_404(client):
    assert client.get("/reports/999").status_code == 404
