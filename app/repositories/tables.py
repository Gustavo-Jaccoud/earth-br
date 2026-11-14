from datetime import datetime

from sqlmodel import Field, SQLModel


class FarmRow(SQLModel, table=True):
    __tablename__ = "farm"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    municipality: str
    state: str
    ibge_code: str | None = None
    owner: str | None = None


class PlotRow(SQLModel, table=True):
    __tablename__ = "plot"
    id: int | None = Field(default=None, primary_key=True)
    farm_id: int = Field(foreign_key="farm.id", index=True)
    name: str
    current_crop: str | None = None
    geometry_json: str
    centroid_lon: float
    centroid_lat: float
    area_ha: float
    in_demo_region: bool


class ReportRow(SQLModel, table=True):
    __tablename__ = "report"
    id: int | None = Field(default=None, primary_key=True)
    plot_id: int = Field(index=True)
    kind: str
    title: str
    sections_json: str
    created_at: datetime
