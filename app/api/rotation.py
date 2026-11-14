from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_farm_or_404_for_plot,
    get_gaez,
    get_plot_or_404,
    get_power_client,
    get_rasters,
)
from app.clients.power import PowerClient
from app.models.farms import Farm, Plot
from app.models.rotation import RotationRequest, RotationResponse
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.services import rotation

router = APIRouter(tags=["rotação"])


@router.post("/plots/{plot_id}/rotation/compare")
def compare_rotation(
    body: RotationRequest,
    plot: Plot = Depends(get_plot_or_404),
    farm: Farm = Depends(get_farm_or_404_for_plot),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    gaez: GaezRepository = Depends(get_gaez),
) -> RotationResponse:
    """Compara sequências de culturas (ex.: milho → feijão) para o talhão: risco hídrico (chuva
    histórica x necessidade da cultura), vigor do solo (NDVI) e aptidão da cultura no local
    (FAO GAEZ)."""
    try:
        return rotation.compare(plot, farm, body, power, rasters, gaez)
    except rotation.UnknownCrop as exc:
        raise HTTPException(422, str(exc)) from exc
