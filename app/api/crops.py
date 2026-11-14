from fastapi import APIRouter

from app.config_loader import get_config
from app.models.crops import Crop

router = APIRouter(tags=["culturas"])


@router.get("/crops")
def list_crops() -> list[Crop]:
    return get_config().crops
