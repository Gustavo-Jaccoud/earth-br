from datetime import date

from fastapi import APIRouter

from app.api import examples
from app.models.signals import SignalsResponse

router = APIRouter(tags=["semáforos"])


@router.get("/plots/{plot_id}/signals")
def get_signals(plot_id: int, reference_date: date | None = None) -> SignalsResponse:
    return examples.SIGNALS
