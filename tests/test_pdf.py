from datetime import datetime, timezone

from app.models.farms import Farm, GeoJSONPolygon, Plot
from app.models.reports import Report, ReportSection
from app.services import pdf
from tests.helpers import install_power, make_plot

SQUARE = GeoJSONPolygon(type="Polygon", coordinates=[[(-37.05, -10.27), (-37.04, -10.27),
                                                      (-37.04, -10.26), (-37.05, -10.26),
                                                      (-37.05, -10.27)]])
PLOT = Plot(id=1, farm_id=1, name="Talhão 1", current_crop="milho", geometry=SQUARE,
            centroid=(-37.045, -10.265), area_ha=121.9, in_demo_region=True)
FARM = Farm(id=1, name="Sítio Demonstração", municipality="Aquidabã", state="SE")


def report(*sections):
    return Report(id=7, plot_id=1, kind="analysis", title="Análise do Talhão 1",
                  created_at=datetime(2026, 11, 14, 12, 30, tzinfo=timezone.utc),
                  sections=list(sections))


def test_pdf_bytes():
    section = ReportSection(title="Condição atual", text="Choveu 15.2 mm.",
                            data={"reference_date": "2026-11-11", "signals": [
                                {"kind": "rain", "color": "red", "value": 15.2, "normal": 41.7}]})
    data = pdf.render_report(report(section), PLOT, FARM)
    assert data.startswith(b"%PDF") and len(data) > 1000


def test_pdf_handles_accents_arrows_and_markup():
    section = ReportSection(
        title="Comparação de rotação",
        text="Milho → Feijão em Aquidabã.\n• Cobertura do solo <b>& palha</x>", data={})
    assert pdf.render_report(report(section), PLOT, FARM).startswith(b"%PDF")


def test_printable_replaces_unsupported_characters():
    assert "→" not in pdf.printable("Milho → Feijão")
    assert pdf.printable("Aquidabã • feijão") == "Aquidabã • feijão"
    assert pdf.printable("日本") == "??"


def test_pdf_without_farm_or_sections():
    assert pdf.render_report(report(), PLOT).startswith(b"%PDF")


def test_pdf_route_for_analysis_and_quiz(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    install_power(client, tmp_path, {"centroid": (-37.05, -10.275)})
    analysis = client.post(f"/plots/{plot['id']}/reports/analysis").json()
    quiz = client.post(f"/plots/{plot['id']}/quiz", json={"answers": {
        "irrigacao": "nao", "cobertura": "nunca", "cultura": "milho", "seca": "mais_metade"}}
    ).json()
    for report_ in (analysis, quiz):
        response = client.get(f"/reports/{report_['id']}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == (
            f'attachment; filename="relatorio-{report_["id"]}.pdf"')
        assert response.content.startswith(b"%PDF") and len(response.content) > 1500


def test_pdf_route_unknown_report_404(client):
    assert client.get("/reports/999/pdf").status_code == 404
