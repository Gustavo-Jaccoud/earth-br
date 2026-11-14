from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api import examples
from app.models.regional import CausesResponse, LossRanking
from app.repositories.ibge import IbgeRepository
from app.services import losses

router = APIRouter(tags=["panorama regional"])


def get_ibge(request: Request) -> IbgeRepository:
    return request.app.state.ibge


@router.get("/regional/losses")
def regional_losses(
    level: Literal["region", "state", "municipality"] = "region",
    code: str = "2",
    repo: IbgeRepository = Depends(get_ibge),
) -> LossRanking:
    """Ranking de culturas por perda média (IBGE PAM). Padrão: Nordeste inteiro."""
    rows = repo.rows(level, code)
    if rows.empty:
        raise HTTPException(404, "Território não encontrado nos dados do IBGE.")
    return LossRanking(
        level=level,
        territory_code=code,
        territory_name=repo.territory_name(level, code),
        period=(int(rows["year"].min()), int(rows["year"].max())),
        source="IBGE PAM",
        items=losses.ranking(rows, min_mean_planted_ha=losses.MIN_PLANTED_HA[level]),
    )


@router.get("/regional/causes")
def regional_causes(crop: str = "milho") -> CausesResponse:
    return examples.CAUSES
