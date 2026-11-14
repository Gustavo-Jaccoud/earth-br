from fastapi import APIRouter

from app.api import examples
from app.models.rotation import RotationRequest, RotationResponse

router = APIRouter(tags=["rotação"])


@router.post("/plots/{plot_id}/rotation/compare")
def compare_rotation(plot_id: int, body: RotationRequest) -> RotationResponse:
    return examples.ROTATION
