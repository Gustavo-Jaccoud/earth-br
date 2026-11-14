from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_farm_or_404, get_farm_repo, get_plot_or_404
from app.models.farms import Farm, FarmCreate, Plot, PlotCreate
from app.repositories.farms import FarmRepository

router = APIRouter(tags=["propriedades"])


@router.post("/farms", status_code=201)
def create_farm(body: FarmCreate, repo: FarmRepository = Depends(get_farm_repo)) -> Farm:
    return repo.create_farm(body)


@router.get("/farms")
def list_farms(repo: FarmRepository = Depends(get_farm_repo)) -> list[Farm]:
    return repo.list_farms()


@router.get("/farms/{farm_id}")
def get_farm(farm: Farm = Depends(get_farm_or_404)) -> Farm:
    return farm


@router.post("/farms/{farm_id}/plots", status_code=201)
def create_plot(
    body: PlotCreate,
    farm: Farm = Depends(get_farm_or_404),
    repo: FarmRepository = Depends(get_farm_repo),
) -> Plot:
    try:
        return repo.create_plot(farm.id, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/farms/{farm_id}/plots")
def list_plots(
    farm: Farm = Depends(get_farm_or_404), repo: FarmRepository = Depends(get_farm_repo)
) -> list[Plot]:
    return repo.list_plots(farm.id)


@router.get("/plots/{plot_id}")
def get_plot(plot: Plot = Depends(get_plot_or_404)) -> Plot:
    return plot
