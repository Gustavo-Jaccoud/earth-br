from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_plot_or_404, get_power_client
from app.clients.power import PowerClient
from app.models.farms import Plot
from app.models.signals import SignalsResponse
from app.services.signals import NoDataForDate, build_signals

router = APIRouter(tags=["semáforos"])


@router.get("/plots/{plot_id}/signals")
def get_signals(
    reference_date: date | None = None,
    plot: Plot = Depends(get_plot_or_404),
    power: PowerClient = Depends(get_power_client),
) -> SignalsResponse:
    """Semáforos de chuva e umidade do solo. `reference_date` além do último dado
    disponível é ajustada automaticamente (`reference_date_adjusted`)."""
    try:
        return build_signals(plot, reference_date, power)
    except NoDataForDate as exc:
        raise HTTPException(422, str(exc)) from exc
