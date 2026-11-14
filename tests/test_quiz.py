import pytest

from app.services.texts import render
from tests.helpers import install_power, make_plot

HIGH = {"q1": "agua", "q2": "perdi", "q3": "pousio", "q4": ["sulcos", "levada"], "q5": "nenhuma",
        "q6": "nao", "q7": "sempre", "q8": "proprio", "q9": "nada",
        "q10": ["agua", "solo", "renda", "animais"]}
LOW = HIGH | {"q1": "renda", "q2": "boa", "q3": "cobertura", "q4": ["nao"], "q5": "irrigacao",
              "q7": "nao", "q9": "consigo"}


@pytest.fixture
def plot(client, tmp_path):
    plot = make_plot(client, crop="milho")
    install_power(client, tmp_path, plot)
    return plot


def submit(client, plot, answers):
    return client.post(f"/plots/{plot['id']}/quiz", json={"answers": answers})


def sections(report):
    return {s["title"]: s for s in report["sections"]}


def test_quiz_questions_have_types_and_hide_internal_fields(client):
    questions = client.get("/quiz").json()
    assert [q["id"] for q in questions] == [f"q{i}" for i in range(1, 11)]
    assert {q["id"]: q["type"] for q in questions} | {"q4": "multi", "q10": "rank"} == {
        q["id"]: q["type"] for q in questions}
    assert sum(q["type"] == "single" for q in questions) == 8
    assert all(set(o) == {"id", "label"} for q in questions for o in q["options"])
    assert all(set(q) == {"id", "text", "type", "options"} for q in questions)


def test_quiz_high_risk_report(client, plot):
    response = submit(client, plot, HIGH)
    assert response.status_code == 201
    report = response.json()
    assert report["kind"] == "quiz" and report["title"] == "Quick start — Talhão 1"
    s = sections(report)
    assert list(s) == ["Risk", "Environmental impact", "Financial impact", "Suggestions"]
    assert s["Risk"]["text"] == render("quiz.risk.high", risk=100)
    assert s["Risk"]["data"]["risk"] == 100 and s["Risk"]["data"]["answers"] == HIGH
    assert len(s["Suggestions"]["data"]["suggestions"]) == 8
    assert "contour" in s["Suggestions"]["text"]
    assert "It rained" in s["Environmental impact"]["text"]


def test_multi_answer_counts_highest_risk_only(client, plot):
    one = sections(submit(client, plot, LOW | {"q4": ["sulcos"]}).json())["Risk"]["data"]["risk"]
    two = sections(submit(client, plot, LOW | {"q4": ["sulcos", "raizes"]}).json())["Risk"]["data"]
    assert one == two["risk"] > 0


def test_quiz_financial_estimate_uses_gaez_yield_and_water_shortfall(client, plot):
    section = sections(submit(client, plot, HIGH).json())["Financial impact"]
    data = section["data"]
    assert data["crop"] == "milho" and data["attainable_yield_kg_ha"] == 2500.0
    assert 0 < data["water_coverage_pct"] < 100  # a média de 2001-2020 inclui anos secos
    expected = plot["area_ha"] * 2500 * (1 - data["water_coverage_pct"] / 100) * 1.2
    assert data["estimated_loss_brl_per_year"] == pytest.approx(expected, rel=0.02)
    assert "maize" in section["text"] and "R$" in section["text"]


def test_quiz_low_risk_without_suggestions(client, plot):
    s = sections(submit(client, plot, LOW).json())
    assert s["Risk"]["text"] == render("quiz.risk.low", risk=0)
    assert s["Suggestions"]["text"] == render("quiz.no_suggestions")


def test_quiz_no_financial_without_gaez_crop(client, tmp_path):
    for crop in ("palma", None):
        plot = make_plot(client, crop=crop)
        install_power(client, tmp_path, plot)
        s = sections(submit(client, plot, LOW).json())
        assert s["Financial impact"]["text"] == render("quiz.no_financial")


def test_quiz_saved_and_listed(client, plot):
    report = submit(client, plot, HIGH).json()
    assert client.get(f"/reports/{report['id']}").json() == report
    assert client.get("/reports").json()[0]["kind"] == "quiz"


def test_quiz_survives_power_outage(client, tmp_path):
    plot = make_plot(client, crop="milho")
    install_power(client, tmp_path, plot, history=False, recent=False)
    s = sections(submit(client, plot, HIGH).json())
    assert s["Environmental impact"]["text"] == render("report.unavailable")
    assert s["Risk"]["data"]["risk"] == 100


@pytest.mark.parametrize("change,question", [
    ({"q9": None}, "q9"),                              # sem resposta
    ({"q5": "talvez"}, "q5"),                          # opção inexistente
    ({"q5": ["nenhuma"]}, "q5"),                       # lista em pergunta de uma opção
    ({"q4": []}, "q4"),                                # multi vazio
    ({"q4": "sulcos"}, "q4"),                          # texto em pergunta multi
    ({"q4": ["sulcos", "sulcos"]}, "q4"),              # repetido
    ({"q10": ["agua", "solo"]}, "q10"),                # ordenação incompleta
    ({"extra": "x"}, "extra"),                         # pergunta desconhecida
])
def test_quiz_invalid_answers_422_and_nothing_saved(client, plot, change, question):
    answers = {k: v for k, v in (HIGH | change).items() if v is not None}
    response = submit(client, plot, answers)
    assert response.status_code == 422 and question in response.json()["detail"]
    assert client.get("/reports").json() == []


def test_quiz_unknown_plot_404(client):
    assert client.post("/plots/999/quiz", json={"answers": HIGH}).status_code == 404
