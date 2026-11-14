import json

from fastapi import APIRouter, HTTPException, Request

from app.models.maps import MapLayerIndex, MapPeriod
from pipeline.layers import LAYERS

router = APIRouter(tags=["mapa"])


@router.get("/maps/{layer}")
def get_map_layer(layer: str, request: Request) -> MapLayerIndex:
    """Camada de mapa (PNG mensal + limites) para sobrepor ao mapa do frontend."""
    index_path = request.app.state.settings.data_dir / "maps" / layer / "index.json"
    if layer not in LAYERS or not index_path.exists():
        raise HTTPException(404, "Camada de mapa não encontrada. Rode o pipeline de mapas.")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    return MapLayerIndex(
        layer=index["layer"], unit=index["unit"], legend=index["legend"],
        periods=[MapPeriod(period=p["period"], bounds=p["bounds"],
                           url=f"/static/maps/{layer}/{p['file']}") for p in index["periods"]],
    )
