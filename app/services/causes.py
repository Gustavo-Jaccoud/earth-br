"""Cruza os anos de maior perda (IBGE) com a anomalia de chuva da estação chuvosa (NASA POWER)."""
from collections.abc import Iterable

import pandas as pd

from app.clients.power import PowerClient
from app.config_loader import get_config
from app.models.regional import CausesResponse, CauseYear
from app.repositories.ibge import IbgeRepository
from app.repositories.region import Region
from app.services import climatology, losses
from app.services.rotation import UnknownCrop
from app.services.texts import render

DROUGHT_ANOMALY_PCT = -20.0  # chuva da estação pelo menos 20% abaixo do normal
TOP_YEARS = 3


class CropWithoutIbgeData(ValueError):
    pass


class NoLossData(LookupError):
    pass


def season_rain_anomaly(history: pd.DataFrame, months: list[int],
                        normal_years: Iterable[int] = climatology.NORMAL_YEARS) -> dict[int, float]:
    """Por ano: (chuva da estação − média nos anos normais) / média × 100."""
    rain = history["PRECTOTCORR"]
    season = rain[rain.index.month.isin(months)].groupby(rain[rain.index.month.isin(months)]
                                                         .index.year).sum()
    base = season[season.index.isin(list(normal_years))].mean()
    return {int(year): float((total - base) / base * 100) for year, total in season.items()}


def loss_years(repo: IbgeRepository, ibge_name: str, region: Region) -> tuple[pd.DataFrame, str]:
    """Perdas por ano da cultura: do município da região; se faltar dado, do estado."""
    for level, code in (("municipality", region.ibge_code), ("state", region.state_code)):
        rows = repo.rows(level, code)
        years = losses.yearly_loss(rows[rows["crop"] == ibge_name])
        if len(years) >= losses.FALLBACK_MIN_YEARS:
            return years, repo.territory_name(level, code)
    raise NoLossData("Sem dados de perda do IBGE para esta cultura na região.")


def build_causes(loss_by_year: pd.DataFrame, anomalies: dict[int, float], crop_name: str,
                 territory_name: str, crop_id: str | None = None) -> CausesResponse:
    years = [
        CauseYear(
            year=int(row.year), loss_pct=round(float(row.loss) * 100, 1),
            rain_anomaly_pct=(round(anomalies[int(row.year)], 1)
                              if int(row.year) in anomalies else None),
        )
        for row in loss_by_year.sort_values("year").itertuples()
    ]
    worst = sorted(years, key=lambda y: y.loss_pct, reverse=True)[:TOP_YEARS]
    sentences = [
        render("causes.year", year=y.year, crop=crop_name.lower(), loss=f"{y.loss_pct:.0f}",
               rain=f"{abs(y.rain_anomaly_pct):.0f}")
        for y in worst
        if y.rain_anomaly_pct is not None and y.rain_anomaly_pct <= DROUGHT_ANOMALY_PCT
    ]
    return CausesResponse(territory_name=territory_name, crop=crop_id or crop_name, years=years,
                          message=" ".join(sentences) if sentences else render("causes.none"))


def explain(crop_id: str, ibge: IbgeRepository, power: PowerClient,
            region: Region) -> CausesResponse:
    by_id = {c.id: c for c in get_config().crops}
    if crop_id not in by_id:
        raise UnknownCrop(
            f"Cultura desconhecida: {crop_id}. Culturas válidas: {', '.join(by_id)}.")
    crop = by_id[crop_id]
    if crop.ibge_name is None:
        raise CropWithoutIbgeData(
            f"{crop.name} não tem dados de produção no IBGE (PAM); escolha outra cultura.")
    loss_by_year, territory = loss_years(ibge, crop.ibge_name, region)
    lon, lat = region.center
    history = power.history(lat, lon)
    anomalies = season_rain_anomaly(history, list(region.rainy_season_months))
    return build_causes(loss_by_year, anomalies, crop.name, territory, crop_id=crop_id)
