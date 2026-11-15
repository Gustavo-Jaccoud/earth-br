import re

import pytest

from app.config_loader import get_config
from app.services import chat

CFG = get_config().chat
TOPIC_IDS = ["rain", "soil_moisture", "temperature", "risk", "dry_years", "crops", "rotation",
             "financial", "reports", "sources", "help", "greeting"]


def topic_of(message):
    found = chat.match(message, CFG)
    return found.id if found else None


def test_config_has_all_topics_with_fallback():
    assert [t.id for t in CFG.topics] == TOPIC_IDS
    assert all(t.fallback.strip() and t.keywords for t in CFG.topics)
    assert CFG.generic.strip()
    assert all(t.answer is None for t in CFG.topics if t.id in TOPIC_IDS[8:])
    assert all(t.answer for t in CFG.topics if t.id in TOPIC_IDS[:8])


def test_fallbacks_and_generic_have_no_digits():
    for text in [CFG.generic, *(t.fallback for t in CFG.topics)]:
        assert not re.search(r"\d", text), text


def test_normalize():
    assert chat.normalize("Como está a CHUVA, hoje?!") == ["como", "esta", "a", "chuva", "hoje"]


@pytest.mark.parametrize("message,topic", [
    ("How is the rain this month?", "rain"), ("choveu pouco?", "rain"),
    ("is my soil dry?", "soil_moisture"), ("umidade do solo", "soil_moisture"),
    ("how hot is it", "temperature"), ("qual a temperatura", "temperature"),
    ("am I at risk?", "risk"),
    ("worst drought years", "dry_years"), ("anos de seca", "dry_years"),
    ("which crops suit my land?", "crops"), ("o que plantar", "crops"),
    ("compare rotation options", "rotation"), ("rotação de culturas", "rotation"),
    ("how much money could I lose?", "financial"), ("prejuízo", "financial"),
    ("download the pdf report", "reports"),
    ("where does the data come from?", "sources"),
    ("what can you do?", "help"),
    ("hello", "greeting"), ("oi", "greeting"),
])
def test_match_english_and_portuguese(message, topic):
    assert topic_of(message) == topic


def test_short_keywords_do_not_match_inside_words():
    assert topic_of("this soil") == "soil_moisture"  # "hi" dentro de "this" não é saudação
    assert topic_of("history") is None


def test_most_keywords_win_and_tie_goes_to_first():
    assert topic_of("rain and soil moisture") == "soil_moisture"
    assert topic_of("rain temperature") == "rain"


@pytest.mark.parametrize("message", ["what is the capital of France?", "🙂", "???"])
def test_unknown_question_is_none(message):
    assert topic_of(message) is None


def test_suggestions_skip_topic_and_wrap():
    by_id = {t.id: t.question for t in CFG.topics}
    assert chat.suggestions(CFG, "rain") == [by_id["soil_moisture"], by_id["temperature"],
                                             by_id["risk"]]
    assert chat.suggestions(CFG, "sources")[0] == by_id["rain"]  # help/greeting não têm pergunta
    assert chat.suggestions(CFG, None, 4)[0] == by_id["rain"]
    assert None not in chat.suggestions(CFG, "financial", 4)
