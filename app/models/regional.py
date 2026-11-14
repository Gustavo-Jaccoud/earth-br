from typing import Literal

from pydantic import BaseModel


class LossRankingItem(BaseModel):
    crop: str
    mean_loss_pct: float
    worst_year: int
    worst_loss_pct: float
    years: int


class LossRanking(BaseModel):
    level: Literal["region", "state", "municipality"]
    territory_code: str
    territory_name: str
    period: tuple[int, int]
    source: str
    items: list[LossRankingItem]


class CauseYear(BaseModel):
    year: int
    loss_pct: float
    rain_anomaly_pct: float | None


class CausesResponse(BaseModel):
    territory_name: str
    crop: str
    years: list[CauseYear]
    message: str
