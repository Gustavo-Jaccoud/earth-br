from pydantic import BaseModel


class Crop(BaseModel):
    id: str
    name: str
    gaez_name: str | None  # nome da cultura no FAO GAEZ; None = sem dado de aptidão
    soil_restoring: bool
    planting_month: int
    kc: list[float]
    price_brl_per_kg: float | None
