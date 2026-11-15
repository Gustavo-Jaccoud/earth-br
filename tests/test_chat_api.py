import re

import pytest

from app.config_loader import get_config
from tests.helpers import install_power, make_plot

CFG = get_config().chat
TOPICS = {t.id: t for t in CFG.topics}
OUTSIDE = [[-45.01, -5.01], [-45.0, -5.01], [-45.0, -5.0], [-45.01, -5.0], [-45.01, -5.01]]


def clean(text):
    return " ".join(text.split())


@pytest.fixture
def plot(client, tmp_path):
    plot = make_plot(client, crop="milho")
    install_power(client, tmp_path, plot)
    return plot


def ask(client, plot, message):
    return client.post(f"/plots/{plot['id']}/chat", json={"message": message})


def test_rain_answer_uses_real_signal(client, plot):
    signal = client.get(f"/plots/{plot['id']}/signals").json()["signals"][0]
    body = ask(client, plot, "How is the rain this month?").json()
    assert body["topic"] == "rain" and body["used_data"] is True
    assert signal["message"] in body["answer"]
    assert body["sources"] == ["NASA POWER"] and len(body["suggestions"]) == 3


@pytest.mark.parametrize("message,topic", [
    ("is my soil dry?", "soil_moisture"), ("how hot is it?", "temperature"),
    ("am I at risk?", "risk"), ("worst drought years", "dry_years"),
    ("which crops suit my land?", "crops"), ("compare rotation options", "rotation"),
    ("how much money could I lose?", "financial"),
])
def test_each_data_topic_answers_with_data(client, plot, message, topic):
    response = ask(client, plot, message)
    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == topic and body["used_data"] is True
    assert re.search(r"\d", body["answer"]) and "{" not in body["answer"]
    assert body["answer"] != clean(TOPICS[topic].fallback)


def test_crops_answer_lists_most_suitable_first(client, plot):
    answer = ask(client, plot, "which crops suit my land?").json()["answer"]
    assert "Sorghum (46 out of 100)" in answer
    assert answer.index("Sorghum") < answer.index("Cassava")


def test_rotation_answer_names_current_crop_and_alternative(client, plot):
    answer = ask(client, plot, "compare rotation options").json()["answer"]
    assert "Maize" in answer and "Sorghum → Common bean" in answer
    totals = re.findall(r"scores (\S+) out of 100", answer)
    assert len(totals) == 2 and all(re.fullmatch(r"\d+", t) for t in totals)  # mesmo formato


def test_rotation_answer_says_when_current_crop_is_already_best(client, plot):
    answer = ask(client, plot, "compare rotation options").json()["answer"]
    current, alternative = (int(t) for t in re.findall(r"scores (\d+) out of 100", answer))
    expected = "already the best option" if current >= alternative else "scores higher than"
    assert expected in answer


def test_signal_sources_come_from_the_signal_itself(client, tmp_path, plot):
    from app.repositories.rasters import RasterStore
    from tests.helpers import make_layer

    make_layer(tmp_path, "precipitation", "2015-01-01", "2026-12-31", source="NASA GPM TESTE")
    client.app.state.rasters = RasterStore(tmp_path)
    assert ask(client, plot, "how is the rain?").json()["sources"] == ["NASA GPM TESTE"]
    assert ask(client, plot, "am I at risk?").json()["sources"] == ["NASA GPM TESTE", "NASA POWER"]


def test_portuguese_question_gets_the_same_topic(client, plot):
    assert ask(client, plot, "como está a chuva?").json()["topic"] == "rain"


@pytest.mark.parametrize("message,topic", [
    ("download the pdf report", "reports"), ("where does the data come from?", "sources"),
    ("what can you do?", "help"), ("hello", "greeting"), ("thank you", "thanks"),
    ("will it rain tomorrow? what is the forecast", "forecast"),
])
def test_fixed_topics(client, plot, message, topic):
    body = ask(client, plot, message).json()
    assert body["topic"] == topic and body["used_data"] is False
    assert body["answer"] == clean(TOPICS[topic].fallback)


@pytest.mark.parametrize("message", ["what is the capital of France?", "🙂", "?!"])
def test_generic_answer_for_unknown_question(client, plot, message):
    body = ask(client, plot, message).json()
    assert body["topic"] == "generic" and body["used_data"] is False
    assert body["answer"] == clean(CFG.generic) and len(body["suggestions"]) == 3


def test_power_outage_falls_back_to_fixed_text(client, tmp_path):
    plot = make_plot(client, crop="milho")
    install_power(client, tmp_path, plot, history=False, recent=False)
    for message, topic in [("how is the rain?", "rain"), ("am I at risk?", "risk"),
                           ("how hot is it?", "temperature"), ("driest years", "dry_years"),
                           ("compare rotation", "rotation"), ("money lose", "financial")]:
        response = ask(client, plot, message)
        assert response.status_code == 200
        body = response.json()
        assert body["topic"] == topic and body["used_data"] is False
        assert body["answer"] == clean(TOPICS[topic].fallback)
        assert not re.search(r"\d", body["answer"])


def test_outside_gaez_area_falls_back(client, tmp_path):
    plot = make_plot(client, OUTSIDE, crop="milho")
    install_power(client, tmp_path, plot)
    body = ask(client, plot, "which crops suit my land?").json()
    assert body["used_data"] is False and body["answer"] == clean(TOPICS["crops"].fallback)


def test_no_current_crop_falls_back(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    for message, topic in [("compare rotation options", "rotation"),
                           ("how much money could I lose?", "financial")]:
        response = ask(client, plot, message)
        assert response.status_code == 200
        assert response.json()["answer"] == clean(TOPICS[topic].fallback)


@pytest.mark.parametrize("body", [{"message": ""}, {"message": "   "}, {"message": "x" * 501}, {}])
def test_invalid_messages_422(client, plot, body):
    assert client.post(f"/plots/{plot['id']}/chat", json=body).status_code == 422


def test_message_is_trimmed_and_500_chars_accepted(client, plot):
    assert ask(client, plot, "  rain  ").json()["topic"] == "rain"
    assert ask(client, plot, "x" * 500).status_code == 200


def test_unknown_plot_404(client):
    assert client.post("/plots/999/chat", json={"message": "rain"}).status_code == 404


def test_chat_intro(client):
    body = client.get("/chat/suggestions").json()
    assert body["greeting"] == clean(TOPICS["greeting"].fallback)
    assert len(body["suggestions"]) == 4 and body["suggestions"][0] == TOPICS["rain"].question
