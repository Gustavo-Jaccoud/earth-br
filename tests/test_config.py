import pytest

from app.config_loader import load_config


def test_config_loads():
    cfg = load_config()
    ids = [c.id for c in cfg.crops]
    assert len(ids) >= 35 and len(set(ids)) == len(ids)
    for crop in ("milho", "feijao", "mandioca", "soja", "algodao", "cana", "sorgo", "sisal"):
        assert crop in ids
    assert {c.category for c in cfg.crops} <= {"grain", "legume", "root", "oilseed", "fibre",
                                               "vegetable", "fruit", "forage", "other"}
    assert all(1 <= c.planting_month <= 12 and all(0 < k <= 1.3 for k in c.kc)
               for c in cfg.crops)
    assert {c.id for c in cfg.crops if c.soil_restoring} == {
        "feijao", "feijao_caupi", "amendoim", "soja", "guandu"}
    assert sum(cfg.rotation.weights.values()) == pytest.approx(1.0)
    assert cfg.signals.rain.window_days == 30
    assert len(cfg.quiz.questions) == 10


def test_every_crop_kc_nonempty():
    assert all(len(c.kc) >= 1 for c in load_config().crops)


def test_phrases_have_required_keys():
    phrases = load_config().phrases
    for key in ["rain.green", "rain.yellow", "rain.red", "rain.dry_season",
                "soil_moisture.green", "soil_moisture.yellow", "soil_moisture.red",
                "rotation.verdict", "rotation.no_data", "dry_years.year", "dry_years.none",
                "quiz.risk.low", "quiz.risk.medium", "quiz.risk.high",
                "quiz.financial", "quiz.no_financial"]:
        assert key in phrases
