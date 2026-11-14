"""Dados de demonstração criados na partida do servidor (SEED_DEMO=1), se o banco está vazio."""
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.models.farms import FarmCreate, PlotCreate
from app.repositories.farms import FarmRepository
from app.repositories.region import Region
from pipeline.seed_demo import FARM, PLOTS


def seed_if_empty(engine: Engine, region: Region) -> bool:
    """Cria a propriedade de demonstração e seus talhões. Não faz nada se já há propriedades."""
    with Session(engine) as session:
        repo = FarmRepository(session, region)
        if repo.list_farms():
            return False
        farm = repo.create_farm(FarmCreate(**FARM))
        for plot in PLOTS:
            repo.create_plot(farm.id, PlotCreate(**plot))
        return True
