from datetime import date

from fastapi import APIRouter

from app.api import examples
from app.models.climate import ClimateResponse

router = APIRouter(tags=["clima"])


@router.get("/plots/{plot_id}/climate")
def get_climate(plot_id: int, start: date | None = None, end: date | None = None
                ) -> ClimateResponse:
    return examples.CLIMATE
