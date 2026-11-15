from datetime import datetime, timezone

from app.models.farms import Farm, GeoJSONPolygon, Plot
from app.models.reports import Report, ReportSection
from app.services import pdf
from tests.helpers import install_power, make_plot

SQUARE = GeoJSONPolygon(type="Polygon", coordinates=[[(-37.05, -10.27), (-37.04, -10.27),
                                                      (-37.04, -10.26), (-37.05, -10.26),
                                                      (-37.05, -10.27)]])
PLOT = Plot(id=1, farm_id=1, name="Talhão 1", current_crop="milho", geometry=SQUARE,
            query_geometry=SQUARE,
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
        "q1": "agua", "q2": "perdi", "q3": "pousio", "q4": ["sulcos"], "q5": "nenhuma",
        "q6": "nao", "q7": "sempre", "q8": "proprio", "q9": "nada",
        "q10": ["agua", "solo", "renda", "animais"]}}
    ).json()
    for report_ in (analysis, quiz):
        response = client.get(f"/reports/{report_['id']}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == (
            f'attachment; filename="report-{report_["id"]}.pdf"')
        assert response.content.startswith(b"%PDF") and len(response.content) > 1500


def test_pdf_route_unknown_report_404(client):
    assert client.get("/reports/999/pdf").status_code == 404


# --- layout, labels and robustness -------------------------------------------------------

SIGNALS = {"plot_id": 1, "reference_date": "2026-11-12", "reference_date_adjusted": True,
           "signals": [
               {"kind": "rain", "color": "red", "value": 16.4, "normal": 40.0,
                "deviation_pct": -58.9, "unit": "mm", "window_days": 30, "source": "NASA POWER",
                "message": "It rained 16.4 mm."},
               {"kind": "soil_moisture", "color": "yellow", "value": 0.253, "normal": 0.438,
                "deviation_pct": None, "unit": "1", "window_days": 7, "source": "NASA SMAP",
                "message": "Soil is dry."}]}


def rotation_data(n_options=4):
    sequences = [["milho", "feijao", "sorgo"], ["sorgo", "feijao_caupi", "mandioca"],
                 ["mandioca", "feijao", "milho"], ["palma", "feijao_caupi", "sorgo"]]
    detail = "Historical rainfall covers 83% of the water the crop needs in the growing months."
    return {"plot_id": 1, "verdict": "Best: Maize → Common bean → Sorghum.", "options": [
        {"crops": crops, "total": 70.0 - rank, "rank": rank, "scores": [
            {"name": "water", "score": 82.7, "source": "NASA POWER", "detail": detail},
            {"name": "soil", "score": None, "source": "NASA MODIS", "detail": "No NDVI data."},
            {"name": "suitability", "score": 41.0, "source": "FAO GAEZ v4", "detail": detail}]}
        for rank, crops in enumerate(sequences[:n_options], start=1)]}


def long_report():
    suggestions = [f"Suggestion {i}: cover the soil with residue or a cover crop, because it "
                   "holds moisture, lowers the soil temperature and prevents erosion → do it."
                   for i in range(1, 41)]
    years = [{"year": y, "rain_mm": 500.0 + y % 7 * 31.5, "rain_anomaly_pct": (y % 9 - 4) * 9.5}
             for y in range(2001, 2021)]
    return report(
        ReportSection(title="Current conditions", text="It rained 16.4 mm. " * 30, data=SIGNALS),
        ReportSection(title="Rotation comparison", text="Best: Maize → Common bean → Sorghum.",
                      data=rotation_data()),
        ReportSection(title="Crop suitability", text="Most suitable crops: Sorghum.", data={
            "plot_id": 1, "source": "FAO GAEZ v4", "period": "1981-2010", "without_data": ["palma"],
            "items": [{"crop": "sorgo", "name": "Sorghum", "suitability": 46.0,
                       "attainable_yield_kg_ha": 1502.0}]}),
        ReportSection(title="Dry years", text="In 2018 it was dry.", data={
            "plot_id": 1, "source": "NASA POWER", "rainy_season_months": [4, 5, 6, 7, 8],
            "years": years, "message": "In 2018 it was dry."}),
        ReportSection(title="Risk", text="High risk (100 out of 100).", data={
            "risk": 100, "level": "high", "answers": {
                "q1": "agua", "q4": ["sulcos", "levada"], "q99": "whatever"}}),
        ReportSection(title="Financial impact", text="Estimated loss: R$ 527.", data={
            "estimated_loss_brl_per_year": 12527, "crop": "milho",
            "attainable_yield_kg_ha": 2544.0, "water_coverage_pct": 96.5}),
        ReportSection(title="Suggestions", text="\n".join(f"• {s}" for s in suggestions),
                      data={"suggestions": suggestions}),
    )


def test_page_count_helper():
    assert pdf.page_count(pdf.render_report(report(), PLOT)) == 1


def test_long_report_spans_several_pages():
    data = pdf.render_report(long_report(), PLOT, FARM)
    assert data.startswith(b"%PDF")
    assert pdf.page_count(data) >= 3


def test_every_known_section_renders_alone_and_with_empty_data():
    for section in long_report().sections:
        assert pdf.page_count(pdf.render_report(report(section), PLOT, FARM)) >= 1
        empty = ReportSection(title=section.title, text="Data unavailable at the moment.", data={})
        assert pdf.page_count(pdf.render_report(report(empty), PLOT, FARM)) == 1


def test_unknown_and_malformed_data_never_crash():
    weird = {"signals": "not a list", "options": [1, None, {"crops": 5, "scores": "x"}],
             "items": [{"name": None}, 7], "years": [{"year": "?"}], "risk": "n/a",
             "answers": [1, 2], "suggestions": {"a": 1}, "estimated_loss_brl_per_year": None,
             "nested": {"deep": [{"deeper": [1, 2, {"x": None}]}]}, "flag": True, "plot_id": 3,
             "rows": [{"some_key": "a" * 300, "other": 1.5, "third": None}, {"some_key": "日本"}],
             "long_text": "word " * 400, "source": 12}
    for title in ("Current conditions", "Rotation comparison", "Crop suitability", "Dry years",
                  "Risk", "Financial impact", "Suggestions", "Something new"):
        section = ReportSection(title=title, text="Text.", data=weird)
        assert pdf.render_report(report(section), PLOT, FARM).startswith(b"%PDF")


def test_characters_outside_cp1252_everywhere():
    farm = Farm(id=1, name="Fazenda 日本 → Ωmega", municipality="São José → 東京", state="SE")
    plot = PLOT.model_copy(update={"name": "Talhão → 東", "current_crop": "カボチャ"})
    section = ReportSection(title="Título → 東京", text="Milho → Feijão ≥ 50% ✓ “ok” – fim",
                            data={"suggestions": ["Plante → colha ✓", "日本語"]})
    rep = report(section).model_copy(update={"title": "Análise → 東京"})
    assert pdf.render_report(rep, plot, farm).startswith(b"%PDF")


def test_very_long_property_and_field_names():
    farm = Farm(id=1, name="Sítio " + "Nossa Senhora da Conceição do Alto Sertão " * 8,
                municipality="Município " * 20, state="SE")
    plot = PLOT.model_copy(update={"name": "Talhão" + "x" * 200})
    rep = report().model_copy(update={"title": "Land analysis — " + plot.name})
    data = pdf.render_report(rep, plot, farm)
    assert data.startswith(b"%PDF") and pdf.page_count(data) == 1


def test_sources_come_from_the_report_data():
    rep = long_report()
    assert pdf.collect_sources(rep.sections) == ["NASA POWER", "NASA SMAP", "FAO GAEZ v4"]
    only_power = report(ReportSection(title="Dry years", text="x", data={"source": "NASA POWER"}))
    assert pdf.collect_sources(only_power.sections) == ["NASA POWER"]
    assert pdf.collect_sources([]) == []
    assert pdf.footer_sources([]) == ""
    assert pdf.footer_sources(only_power.sections) == "Data sources: NASA POWER"


def test_sources_skip_criteria_without_a_score():
    section = ReportSection(title="Rotation comparison", text="x", data=rotation_data(2))
    assert "NASA MODIS" not in pdf.collect_sources([section])


def test_labels_are_human_readable():
    assert pdf.crop_name("feijao_caupi") == "Cowpea"
    assert pdf.crop_name("abobora_doce") == "Abobora doce"
    assert pdf.crop_sequence(["milho", "feijao"]) == "Maize › Common bean"
    assert pdf.status_label("red") == "Critical"
    assert pdf.status_label("yellow") == "Attention"
    assert pdf.status_label("green") == "Normal"
    assert pdf.status_label("purple") == "Purple"
    assert pdf.label("rain_anomaly_pct") == "Rain anomaly (%)"
    assert pdf.label("attainable_yield_kg_ha") == "Attainable yield (kg/ha)"
    assert pdf.label("reference_date_adjusted") == "Reference date adjusted"


def test_value_formatting():
    assert pdf.fmt_number(2544.0, 0) == "2,544"
    assert pdf.fmt_number(16.44, 1) == "16.4"
    assert pdf.fmt_number(None) == "n/a"
    assert pdf.fmt_number("abc") == "abc"
    assert pdf.fmt_percent(-58.9, signed=True) == "-58.9%"
    assert pdf.fmt_percent(22.8, signed=True) == "+22.8%"
    assert pdf.fmt_percent(None) == "n/a"
    assert pdf.fmt_value(True) == "Yes"
    assert pdf.fmt_value(None) == "n/a"
    assert pdf.fmt_value(["a", "b"]) == "a, b"
    assert pdf.fmt_value("2026-11-12") == "12 Nov 2026"
    assert pdf.fmt_signal_value(0.253, "1") == "25%"
    assert pdf.fmt_signal_value(16.4, "mm") == "16.4 mm"
    assert pdf.fmt_months([4, 5, 6, 7, 8]) == "April–August"
    assert pdf.fmt_months([11, 12, 1]) == "November–January"
    assert pdf.fmt_months([]) == ""
    assert pdf.fmt_datetime(datetime(2026, 11, 14, 12, 30, tzinfo=timezone.utc)) == (
        "14 Nov 2026, 12:30 UTC")


def test_logo_is_bundled_and_embedded():
    assert pdf.LOGO_PATH.read_bytes().startswith(b"\x89PNG")
    assert b"/Subtype /Image" in pdf.render_report(report(), PLOT, FARM)


def test_pdf_is_stored_when_the_report_is_created_and_served_from_disk(client, tmp_path, settings):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    report = client.post(f"/plots/{plot['id']}/reports/analysis").json()
    stored = settings.var_dir / "reports" / f"{report['id']}.pdf"
    assert stored.exists() and stored.read_bytes().startswith(b"%PDF")
    assert client.get(f"/reports/{report['id']}/pdf").content == stored.read_bytes()
    stored.unlink()  # arquivo perdido: é gerado e guardado de novo
    assert client.get(f"/reports/{report['id']}/pdf").content.startswith(b"%PDF")
    assert stored.exists()


def test_rotation_section_heading_is_guarded_against_being_left_alone_on_a_page():
    from reportlab.platypus import CondPageBreak, KeepTogether

    scores = [{"name": n, "score": 50.0, "source": "NASA POWER", "detail": "Detail text."}
              for n in ("water", "soil", "suitability")]
    options = [{"crops": ["milho"], "scores": scores, "total": 50.0, "rank": i} for i in (1, 2, 3)]
    section = ReportSection(title="Crop recommendations", text="The best option is Maize.",
                            data={"options": options, "verdict": "x", "current": ["milho"]})
    flowables = pdf._section(section)
    assert isinstance(flowables[0], (CondPageBreak, KeepTogether))  # nunca o título solto
    assert pdf._height(pdf._section_body(section)) > 0  # mede blocos agrupados sem falhar
