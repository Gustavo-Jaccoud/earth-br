from datetime import date
from typing import Literal

from fastapi import APIRouter

from app.api import examples
from app.models.satellite import SatelliteSeries

router = APIRouter(tags=["satélite"])


@router.get("/plots/{plot_id}/satellite/{layer}")
def get_satellite(plot_id: int, layer: Literal["ndvi", "soil_moisture", "precipitation"],
                  start: date | None = None, end: date | None = None) -> SatelliteSeries:
    return examples.SATELLITE
