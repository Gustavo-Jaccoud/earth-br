from typing import Literal

from fastapi import APIRouter

from app.api import examples
from app.models.regional import CausesResponse, LossRanking

router = APIRouter(tags=["panorama regional"])


@router.get("/regional/losses")
def regional_losses(level: Literal["region", "state", "municipality"] = "region",
                    code: str = "2") -> LossRanking:
    return examples.LOSSES


@router.get("/regional/causes")
def regional_causes(crop: str = "milho") -> CausesResponse:
    return examples.CAUSES
