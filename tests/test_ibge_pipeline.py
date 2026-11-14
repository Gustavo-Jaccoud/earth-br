import copy
import json

import httpx
import pandas as pd
import respx

from pipeline import ibge_pam
from tests.helpers import FIXTURES

SAMPLE = json.loads((FIXTURES / "sidra_sample.json").read_text())


def test_parse_sidra_pivots_variables():
    rows = ibge_pam.parse_sidra(SAMPLE, "municipality")
    assert len(rows) == 2
    milho = next(r for r in rows if r["crop"] == "Milho (em grão)")
    assert milho == {
        "level": "municipality", "territory_code": "2800209",
        "territory_name": "Aquidabã (SE)", "crop": "Milho (em grão)", "year": 2012,
        "planted_ha": 700.0, "harvested_ha": 700.0, "production": 1400.0,
        "production_unit": "Toneladas", "yield_kg_ha": 2000.0,
    }


def test_parse_sidra_missing_markers_become_none():
    rows = copy.deepcopy(SAMPLE)
    for r in rows[1:]:
        if r["D4N"].startswith("Feijão") and r["D2C"] in ("216", "112"):
            r["V"] = "-"
        if r["D4N"].startswith("Feijão") and r["D2C"] == "214":
            r["V"] = "..."
    feijao = next(r for r in ibge_pam.parse_sidra(rows, "municipality")
                  if r["crop"].startswith("Feij"))
    assert feijao["harvested_ha"] is None and feijao["yield_kg_ha"] is None
    assert feijao["production"] is None and feijao["planted_ha"] == 265.0


def test_parse_sidra_skips_total_and_empty_rows():
    rows = copy.deepcopy(SAMPLE)
    total = copy.deepcopy(rows[1]) | {"D4C": "0", "D4N": "Total"}
    empty = [copy.deepcopy(r) | {"D4C": "99", "D4N": "Nada", "V": "-"} for r in rows[1:]]
    assert len(ibge_pam.parse_sidra(rows + [total] + empty, "municipality")) == 2


@respx.mock
def test_main_writes_three_levels(tmp_path):
    route = respx.get(url__regex=r"https://apisidra\.ibge\.gov\.br/values/.*").mock(
        return_value=httpx.Response(200, json=SAMPLE))
    out = tmp_path / "ibge" / "pam.csv"
    ibge_pam.main(start_year=2012, end_year=2013, out=out)
    assert route.call_count == 6  # 3 níveis x 2 anos
    df = pd.read_csv(out, dtype={"territory_code": str})
    assert set(df["level"]) == {"region", "state", "municipality"}
    assert list(df.columns) == ibge_pam.COLUMNS
    urls = [str(c.request.url) for c in route.calls]
    assert any("/n2/2/" in u for u in urls)
    assert any("/n3/21,22,23,24,25,26,27,28,29/" in u for u in urls)
    assert any("/n6/in%20n3%2028/" in u for u in urls)


@respx.mock
def test_main_retries_transient_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(ibge_pam.time, "sleep", lambda _: None)
    respx.get(url__regex=r"https://apisidra\.ibge\.gov\.br/values/.*").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=SAMPLE)] + [
            httpx.Response(200, json=SAMPLE)] * 2)
    ibge_pam.main(start_year=2012, end_year=2012, out=tmp_path / "pam.csv")
    assert (tmp_path / "pam.csv").exists()
