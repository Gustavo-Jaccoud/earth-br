from typing import Literal

from pydantic import BaseModel


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]]  # [anel][ponto] = (lon, lat)


class FarmCreate(BaseModel):
    name: str
    municipality: str
    state: str
    ibge_code: str | None = None
    owner: str | None = None


class Farm(FarmCreate):
    id: int


class PlotCreate(BaseModel):
    name: str
    current_crop: str | None = None
    geometry: GeoJSONPolygon


class Plot(PlotCreate):
    id: int
    farm_id: int
    centroid: tuple[float, float]  # (lon, lat)
    area_ha: float
    in_demo_region: bool
