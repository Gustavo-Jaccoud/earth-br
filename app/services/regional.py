from app.clients.power import PowerClient
from app.config_loader import get_config
from app.models.farms import Plot
from app.models.regional import DryYear, DryYearsResponse, SuitabilityItem, SuitabilityRanking
from app.repositories.gaez import PERIOD, SOURCE, GaezRepository
from app.services import dry_years
from app.services.texts import render


def suitability_ranking(plot: Plot, gaez: GaezRepository) -> SuitabilityRanking:
    """Culturas ordenadas pela aptidão (FAO GAEZ) no local do talhão, da mais apta à menos."""
    lon, lat = plot.centroid
    items, without = [], []
    for crop in get_config().crops:
        found = gaez.at(crop.gaez_name, lat, lon)
        if found is None:
            without.append(crop.id)
        else:
            items.append(SuitabilityItem(crop=crop.id, name=crop.name, suitability=found[0],
                                         attainable_yield_kg_ha=found[1]))
    items.sort(key=lambda i: i.suitability, reverse=True)
    return SuitabilityRanking(plot_id=plot.id, source=SOURCE, period=PERIOD, items=items,
                              without_data=without)


def dry_years_report(plot: Plot, power: PowerClient) -> DryYearsResponse:
    """Chuva da estação chuvosa do local, ano a ano, contra a normal 2001-2020."""
    lon, lat = plot.centroid
    history = power.history(lat, lon)
    months = dry_years.rainy_season(history)
    totals = dry_years.season_totals(history, months)
    anomalies = dry_years.anomalies(history, months)
    years = [DryYear(year=y, rain_mm=round(totals[y], 1), rain_anomaly_pct=round(anomalies[y], 1))
             for y in sorted(totals)]
    driest = sorted(years, key=lambda y: y.rain_anomaly_pct)[:dry_years.TOP_YEARS]
    sentences = [render("dry_years.year", year=y.year, rain=f"{abs(y.rain_anomaly_pct):.0f}",
                        mm=f"{y.rain_mm:.0f}")
                 for y in driest if y.rain_anomaly_pct <= dry_years.DROUGHT_ANOMALY_PCT]
    return DryYearsResponse(plot_id=plot.id, source="NASA POWER", rainy_season_months=months,
                            years=years,
                            message=" ".join(sentences) or render("dry_years.none"))
