from pathlib import Path

import pandas as pd

EMPTY_COLUMNS = ["level", "territory_code", "territory_name", "crop", "year", "planted_ha",
                 "harvested_ha", "production", "production_unit", "yield_kg_ha"]


class IbgeRepository:
    """Lê data/ibge/pam.csv (gerado por pipeline.ibge_pam)."""

    def __init__(self, data_dir: Path):
        path = Path(data_dir) / "ibge" / "pam.csv"
        if path.exists():
            self.df = pd.read_csv(path, dtype={"territory_code": str})
        else:
            self.df = pd.DataFrame(columns=EMPTY_COLUMNS)

    def rows(self, level: str, code: str) -> pd.DataFrame:
        df = self.df
        return df[(df["level"] == level) & (df["territory_code"] == str(code))]

    def territory_name(self, level: str, code: str) -> str | None:
        rows = self.rows(level, code)
        return None if rows.empty else str(rows["territory_name"].iloc[0])
