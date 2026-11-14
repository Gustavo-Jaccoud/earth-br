from pydantic import BaseModel


class SuitabilityItem(BaseModel):
    crop: str
    name: str
    suitability: float  # 0..100
    attainable_yield_kg_ha: float  # matéria seca


class SuitabilityRanking(BaseModel):
    plot_id: int
    source: str
    period: str
    items: list[SuitabilityItem]
    without_data: list[str]


class DryYear(BaseModel):
    year: int
    rain_mm: float
    rain_anomaly_pct: float


class DryYearsResponse(BaseModel):
    plot_id: int
    source: str
    rainy_season_months: list[int]
    years: list[DryYear]
    message: str
