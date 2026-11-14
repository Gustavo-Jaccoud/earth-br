from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.models.farms import Farm, Plot
from app.repositories.farms import FarmRepository
from app.repositories.region import Region, load_region


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_region(request: Request) -> Region:
    return request.app.state.region


def get_farm_repo(
    session: Session = Depends(get_session), region: Region = Depends(get_region)
) -> FarmRepository:
    return FarmRepository(session, region)


def get_farm_or_404(farm_id: int, repo: FarmRepository = Depends(get_farm_repo)) -> Farm:
    farm = repo.get_farm(farm_id)
    if farm is None:
        raise HTTPException(404, "Propriedade não encontrada.")
    return farm


def get_plot_or_404(plot_id: int, repo: FarmRepository = Depends(get_farm_repo)) -> Plot:
    plot = repo.get_plot(plot_id)
    if plot is None:
        raise HTTPException(404, "Talhão não encontrado.")
    return plot


__all__ = ["get_session", "get_region", "get_farm_repo", "get_farm_or_404", "get_plot_or_404",
           "load_region"]
