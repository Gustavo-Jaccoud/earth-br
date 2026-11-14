from fastapi import APIRouter

from app.api import examples
from app.models.maps import MapLayerIndex

router = APIRouter(tags=["mapa"])


@router.get("/maps/{layer}")
def get_map_layer(layer: str) -> MapLayerIndex:
    return examples.MAP
