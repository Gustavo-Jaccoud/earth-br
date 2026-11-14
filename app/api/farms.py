from fastapi import APIRouter

from app.api import examples
from app.models.farms import Farm, FarmCreate, Plot, PlotCreate

router = APIRouter(tags=["propriedades"])


@router.post("/farms", status_code=201)
def create_farm(body: FarmCreate) -> Farm:
    return examples.FARM


@router.get("/farms")
def list_farms() -> list[Farm]:
    return [examples.FARM]


@router.get("/farms/{farm_id}")
def get_farm(farm_id: int) -> Farm:
    return examples.FARM


@router.post("/farms/{farm_id}/plots", status_code=201)
def create_plot(farm_id: int, body: PlotCreate) -> Plot:
    return examples.PLOT


@router.get("/farms/{farm_id}/plots")
def list_plots(farm_id: int) -> list[Plot]:
    return [examples.PLOT]


@router.get("/plots/{plot_id}")
def get_plot(plot_id: int) -> Plot:
    return examples.PLOT
