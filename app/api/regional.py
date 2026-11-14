from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_ibge, get_power_client, get_region
from app.clients.power import PowerClient
from app.models.regional import CausesResponse, LossRanking
from app.repositories.ibge import IbgeRepository
from app.repositories.region import Region
from app.services import causes, losses, rotation

router = APIRouter(tags=["panorama regional"])


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
def regional_causes(
    crop: str = "milho",
    ibge: IbgeRepository = Depends(get_ibge),
    power: PowerClient = Depends(get_power_client),
    region: Region = Depends(get_region),
) -> CausesResponse:
    """Perdas da cultura na região de demonstração, ano a ano, ao lado da anomalia de chuva
    da estação chuvosa (NASA POWER) — mostra quais perdas coincidem com seca."""
    try:
        return causes.explain(crop, ibge, power, region)
    except (rotation.UnknownCrop, causes.CropWithoutIbgeData) as exc:
        raise HTTPException(422, str(exc)) from exc
    except causes.NoLossData as exc:
        raise HTTPException(404, str(exc)) from exc
