import pytest

from app.config_loader import load_config


def test_config_loads():
    cfg = load_config()
    assert len(cfg.crops) == 6
    assert sum(cfg.rotation.weights.values()) == pytest.approx(1.0)
    assert cfg.signals.rain.window_days == 30
    assert len(cfg.quiz.questions) == 4


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
