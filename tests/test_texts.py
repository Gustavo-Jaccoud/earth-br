import pytest

from app.services.texts import render


def test_render_fills_values():
    text = render("rain.red", value="12", days=30, deviation="60%", normal="30")
    assert "12 mm" in text and "30 dias" in text


def test_render_unknown_key_raises():
    with pytest.raises(KeyError):
        render("nao.existe")
