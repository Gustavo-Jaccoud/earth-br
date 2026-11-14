from fastapi import APIRouter, Depends

from app.api.deps import get_gaez, get_plot_or_404, get_power_client
from app.clients.power import PowerClient
from app.models.farms import Plot
from app.models.regional import DryYearsResponse, SuitabilityRanking
from app.repositories.gaez import GaezRepository
from app.services import regional

router = APIRouter(tags=["panorama do local"])


@router.get("/plots/{plot_id}/suitability")
def plot_suitability(plot: Plot = Depends(get_plot_or_404),
                     gaez: GaezRepository = Depends(get_gaez)) -> SuitabilityRanking:
    """Culturas ordenadas pela aptidão ao clima e solo do local, em sequeiro e com baixo uso de
    insumos (FAO GAEZ v4, clima 1981-2010), com o rendimento atingível em kg de matéria seca
    por hectare. `without_data` lista as culturas que o GAEZ não cobre neste ponto."""
    return regional.suitability_ranking(plot, gaez)


@router.get("/plots/{plot_id}/dry-years")
def plot_dry_years(plot: Plot = Depends(get_plot_or_404),
                   power: PowerClient = Depends(get_power_client)) -> DryYearsResponse:
    """Chuva da estação chuvosa do local (os 5 meses seguidos mais chuvosos), ano a ano, e o
    desvio em relação à normal de 2001-2020. Destaca os anos mais secos."""
    return regional.dry_years_report(plot, power)
