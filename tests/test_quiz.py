import pytest

from app.repositories.ibge import IbgeRepository
from app.services import losses
from app.services.texts import render
from tests.helpers import FIXTURES, install_power, make_plot

HIGH = {"irrigacao": "nao", "cobertura": "nunca", "cultura": "milho", "seca": "mais_metade"}
LOW = {"irrigacao": "sim", "cobertura": "sempre", "cultura": "sorgo", "seca": "nenhuma"}


@pytest.fixture
def plot(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    return plot


def submit(client, plot, answers):
    return client.post(f"/plots/{plot['id']}/quiz", json={"answers": answers})


def sections(report):
    return {s["title"]: s for s in report["sections"]}


def test_quiz_questions_hide_internal_fields(client):
    questions = client.get("/quiz").json()
    assert [q["id"] for q in questions] == ["irrigacao", "cobertura", "cultura", "seca"]
    assert all(set(o) == {"id", "label"} for q in questions for o in q["options"])
    assert all(set(q) == {"id", "text", "options"} for q in questions)


def test_quiz_high_risk_report(client, plot):
    response = submit(client, plot, HIGH)
    assert response.status_code == 201
    report = response.json()
    assert report["kind"] == "quiz" and report["title"] == "Partida rápida do Talhão 1"
    s = sections(report)
    assert list(s) == ["Risco", "Impacto ambiental", "Impacto financeiro", "Sugestões"]
    assert s["Risco"]["text"] == render("quiz.risk.high", risk=100)
    assert s["Risco"]["data"]["risk"] == 100
    assert len(s["Sugestões"]["data"]["suggestions"]) == 4
    assert "captação" in s["Sugestões"]["text"]
    assert "Choveu" in s["Impacto ambiental"]["text"]


def test_quiz_financial_estimate_uses_regional_loss(client, plot):
    s = sections(submit(client, plot, HIGH).json())
    # 18,3% de perda média (fixture IBGE) x rendimento mediano 2000 kg/ha x R$ 1,20/kg x área
    expected = f"{plot['area_ha'] * 2000 * 0.183 * 1.2:,.0f}".replace(",", ".")
    assert f"R$ {expected}" in s["Impacto financeiro"]["text"]
    assert "milho" in s["Impacto financeiro"]["text"]


def test_quiz_low_risk_without_suggestions_or_ibge_crop(client, plot):
    s = sections(submit(client, plot, LOW).json())
    assert s["Risco"]["text"] == render("quiz.risk.low", risk=0)
    assert s["Sugestões"]["text"] == render("quiz.no_suggestions")
    assert s["Impacto financeiro"]["text"] == render("quiz.no_financial")  # sorgo sem dado no IBGE


def test_quiz_medium_risk(client, plot):
    answers = {"irrigacao": "parcial", "cobertura": "as_vezes", "cultura": "feijao",
               "seca": "ate_metade"}
    assert sections(submit(client, plot, answers).json())["Risco"]["data"]["level"] == "medium"


def test_quiz_saved_and_listed(client, plot):
    report = submit(client, plot, HIGH).json()
    assert client.get(f"/reports/{report['id']}").json() == report
    assert client.get("/reports").json()[0]["kind"] == "quiz"


def test_quiz_survives_power_outage(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot, history=False, recent=False)
    s = sections(submit(client, plot, HIGH).json())
    assert s["Impacto ambiental"]["text"] == render("report.unavailable")
    assert s["Risco"]["data"]["risk"] == 100


def test_quiz_missing_answer_422_and_nothing_saved(client, plot):
    answers = {k: v for k, v in HIGH.items() if k != "seca"}
    response = submit(client, plot, answers)
    assert response.status_code == 422 and "seca" in response.json()["detail"]
    assert client.get("/reports").json() == []


def test_quiz_invalid_option_422(client, plot):
    response = submit(client, plot, HIGH | {"irrigacao": "talvez"})
    assert response.status_code == 422 and "irrigacao" in response.json()["detail"]


def test_quiz_unknown_question_422(client, plot):
    response = submit(client, plot, HIGH | {"extra": "x"})
    assert response.status_code == 422 and "extra" in response.json()["detail"]


def test_quiz_unknown_plot_404(client):
    assert client.post("/plots/999/quiz", json={"answers": HIGH}).status_code == 404


def test_crop_median_yield_with_fallback():
    repo = IbgeRepository(FIXTURES / "data")
    assert losses.crop_median_yield(repo, "Milho (em grão)", "2800209", "28") == 2000.0
    assert losses.crop_median_yield(repo, "Milho (em grão)", "9999999", "28") == 2000.0
    assert losses.crop_median_yield(repo, "Palma", "2800209", "28") is None
