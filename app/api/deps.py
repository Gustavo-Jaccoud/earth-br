from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.clients.power import PowerClient
from app.models.farms import Farm, Plot
from app.repositories.farms import FarmRepository
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.repositories.region import Region
from app.repositories.reports import ReportRepository


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_power_client(request: Request) -> PowerClient:
    return request.app.state.power


def get_rasters(request: Request) -> RasterStore:
    return request.app.state.rasters


def get_gaez(request: Request) -> GaezRepository:
    return request.app.state.gaez


def get_report_repo(session: Session = Depends(get_session)) -> ReportRepository:
    return ReportRepository(session)


def get_region(request: Request) -> Region:
    return request.app.state.region


def get_farm_repo(
    session: Session = Depends(get_session), region: Region = Depends(get_region)
) -> FarmRepository:
    return FarmRepository(session, region)


def get_farm_or_404(farm_id: int, repo: FarmRepository = Depends(get_farm_repo)) -> Farm:
    farm = repo.get_farm(farm_id)
    if farm is None:
        raise HTTPException(404, "Property not found.")
    return farm


def get_plot_or_404(plot_id: int, repo: FarmRepository = Depends(get_farm_repo)) -> Plot:
    plot = repo.get_plot(plot_id)
    if plot is None:
        raise HTTPException(404, "Field not found.")
    return plot



def get_farm_or_404_for_plot(
    plot: Plot = Depends(get_plot_or_404), repo: FarmRepository = Depends(get_farm_repo)
) -> Farm:
    farm = repo.get_farm(plot.farm_id)
    if farm is None:
        raise HTTPException(404, "Property not found.")
    return farm
