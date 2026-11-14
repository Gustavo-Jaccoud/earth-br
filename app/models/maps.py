from pydantic import BaseModel


class LegendItem(BaseModel):
    color: str
    label: str


class MapPeriod(BaseModel):
    period: str  # YYYY-MM
    url: str
    bounds: list[list[float]]  # [[south, west], [north, east]]


class MapLayerIndex(BaseModel):
    layer: str
    unit: str
    legend: list[LegendItem]
    periods: list[MapPeriod]
