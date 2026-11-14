"""Baixa a Produção Agrícola Municipal (IBGE/SIDRA, tabela 5457) e grava data/ibge/pam.csv.

Uso:  python -m pipeline.ibge_pam            (anos 2010-2023)
Níveis: Nordeste (região), UFs do Nordeste e municípios de Sergipe (o SIDRA limita cada consulta
a 100 mil valores, então o nível municipal cobre só a UF da região de demonstração).
"""
import csv
import time
from pathlib import Path

import httpx

SIDRA = "https://apisidra.ibge.gov.br/values/t/5457"
VARIABLES = "8331,216,214,112"  # área plantada, área colhida, produção, rendimento
NE_STATES = "21,22,23,24,25,26,27,28,29"
LEVELS = [
    ("region", "n2/2"),
    ("state", f"n3/{NE_STATES}"),
    ("municipality", "n6/in%20n3%2028"),
]
COLUMNS = ["level", "territory_code", "territory_name", "crop", "year", "planted_ha",
           "harvested_ha", "production", "production_unit", "yield_kg_ha"]
FIELD_BY_VARIABLE = {"8331": "planted_ha", "216": "harvested_ha", "214": "production",
                     "112": "yield_kg_ha"}
MISSING = {"-", "..", "...", "X", ""}
RETRIES = 3


def _number(value: str) -> float | None:
    return None if value in MISSING else float(value)


def parse_sidra(rows: list[dict], level: str) -> list[dict]:
    """Pivota as linhas do SIDRA (uma por variável) em uma linha por território/cultura/ano."""
    pivot: dict[tuple, dict] = {}
    for r in rows:
        if r.get("NC") == "Nível Territorial (Código)":  # linha de cabeçalho
            continue
        if r["D4C"] == "0":  # "Total" de todas as lavouras
            continue
        key = (r["D1C"], r["D4C"], r["D3C"])
        item = pivot.setdefault(key, {
            "level": level, "territory_code": r["D1C"], "territory_name": r["D1N"],
            "crop": r["D4N"], "year": int(r["D3C"]), "planted_ha": None, "harvested_ha": None,
            "production": None, "production_unit": None, "yield_kg_ha": None,
        })
        field = FIELD_BY_VARIABLE.get(r["D2C"])
        if field:
            item[field] = _number(r["V"])
        if r["D2C"] == "214":
            item["production_unit"] = r["MN"]
    numeric = ("planted_ha", "harvested_ha", "production", "yield_kg_ha")
    return [i for i in pivot.values() if any(i[f] is not None for f in numeric)]


def _fetch(client: httpx.Client, path: str, year: int) -> list[dict]:
    url = f"{SIDRA}/{path}/v/{VARIABLES}/p/{year}/c782/all"
    for attempt in range(1, RETRIES + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            if attempt == RETRIES:
                raise
            time.sleep(2 * attempt)
    return []


def main(start_year: int = 2010, end_year: int = 2023, out: Path = Path("data/ibge/pam.csv"),
         client: httpx.Client | None = None) -> Path:
    client = client or httpx.Client(timeout=120)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for year in range(start_year, end_year + 1):
            for level, path in LEVELS:
                rows = parse_sidra(_fetch(client, path, year), level)
                writer.writerows(rows)
                total += len(rows)
                print(f"{year} {level}: {len(rows)} linhas")
    print(f"{total} linhas gravadas em {out}")
    return out


if __name__ == "__main__":
    main()
