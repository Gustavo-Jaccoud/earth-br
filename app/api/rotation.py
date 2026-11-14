from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_farm_or_404_for_plot,
    get_ibge,
    get_plot_or_404,
    get_power_client,
    get_rasters,
    get_region,
)
from app.clients.power import PowerClient
from app.models.farms import Farm, Plot
from app.models.rotation import RotationRequest, RotationResponse
from app.repositories.ibge import IbgeRepository
from app.repositories.rasters import RasterStore
from app.repositories.region import Region
from app.services import rotation

router = APIRouter(tags=["rotação"])


@router.post("/plots/{plot_id}/rotation/compare")
def compare_rotation(
    body: RotationRequest,
    plot: Plot = Depends(get_plot_or_404),
    farm: Farm = Depends(get_farm_or_404_for_plot),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    ibge: IbgeRepository = Depends(get_ibge),
    region: Region = Depends(get_region),
) -> RotationResponse:
    """Compara sequências de culturas (ex.: milho → feijão) para o talhão: risco hídrico (chuva
    histórica x necessidade da cultura), vigor do solo (NDVI) e perda regional (IBGE)."""
    try:
        return rotation.compare(plot, farm, body, power, rasters, ibge, region)
    except rotation.UnknownCrop as exc:
        raise HTTPException(422, str(exc)) from exc
