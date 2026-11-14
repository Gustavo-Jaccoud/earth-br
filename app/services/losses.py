import pandas as pd

from app.models.regional import LossRankingItem
from app.repositories.ibge import IbgeRepository

MIN_PLANTED_HA = {"region": 10_000, "state": 1_000, "municipality": 10}
FALLBACK_MIN_YEARS = 3


def yearly_loss(df: pd.DataFrame) -> pd.DataFrame:
    """Perda por (cultura, ano) de UM território: 1 − produção / (área plantada × rendimento
    mediano da cultura no território), limitada a 0..1. Só produção em toneladas."""
    d = df[(df["production_unit"] == "Toneladas") & (df["planted_ha"] > 0)].copy()
    d["production_kg"] = d["production"] * 1000
    median = d[d["yield_kg_ha"] > 0].groupby("crop")["yield_kg_ha"].median()
    d = d.join(median.rename("median_yield"), on="crop")
    d = d.dropna(subset=["production_kg", "median_yield"])
    d["loss"] = (1 - d["production_kg"] / (d["planted_ha"] * d["median_yield"])).clip(0, 1)
    return d[["crop", "year", "planted_ha", "loss"]].reset_index(drop=True)


def ranking(df: pd.DataFrame, min_years: int = 5,
            min_mean_planted_ha: float = 0.0) -> list[LossRankingItem]:
    """Culturas ordenadas pela perda média (maior primeiro)."""
    items = []
    for crop, group in yearly_loss(df).groupby("crop"):
        if len(group) < min_years or group["planted_ha"].mean() < min_mean_planted_ha:
            continue
        worst = group.loc[group["loss"].idxmax()]
        items.append(LossRankingItem(
            crop=str(crop),
            mean_loss_pct=round(float(group["loss"].mean()) * 100, 1),
            worst_year=int(worst["year"]),
            worst_loss_pct=round(float(worst["loss"]) * 100, 1),
            years=len(group),
        ))
    return sorted(items, key=lambda i: i.mean_loss_pct, reverse=True)


def crop_loss_pct(repo: IbgeRepository, ibge_name: str, municipality_code: str | None,
                  state_code: str) -> tuple[float, str] | None:
    """Perda média (%) da cultura no município; se faltar dado, no estado. (pct, nível usado)."""
    for level, code in (("municipality", municipality_code), ("state", state_code)):
        if not code:
            continue
        rows = repo.rows(level, code)
        losses = yearly_loss(rows[rows["crop"] == ibge_name])
        if len(losses) >= FALLBACK_MIN_YEARS:
            return round(float(losses["loss"].mean()) * 100, 1), level
    return None
