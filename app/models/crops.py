from pydantic import BaseModel


class Crop(BaseModel):
    id: str
    name: str
    ibge_name: str | None
    soil_restoring: bool
    planting_month: int
    kc: list[float]
    price_brl_per_kg: float | None
