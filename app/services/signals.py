from collections.abc import Iterable
from datetime import date, timedelta

import pandas as pd

from app.clients.power import (
    HISTORY_END,
    HISTORY_START,
    PowerClient,
    last_available_date,
)
from app.config_loader import RainConfig, SoilMoistureConfig, Thresholds, get_config
from app.models.farms import Plot
from app.models.signals import Signal, SignalsResponse
from app.repositories.rasters import RasterStore
from app.services import climatology, geometry
from app.services.texts import render

POWER = "NASA POWER"


class NoDataForDate(ValueError):
    """Não há dados suficientes para calcular o semáforo na data de referência."""


def classify(deviation_pct: float, thresholds: Thresholds) -> str:
    if deviation_pct <= thresholds.red:
        return "red"
    if deviation_pct <= thresholds.yellow:
        return "yellow"
    return "green"


def _value_and_normal(series, normal_series, years, reference, days, agg, source):
    value = climatology.window(series, reference, days, agg)
    normal = climatology.normal(normal_series, reference, days, years, agg)
    if value is None or normal is None:
        raise NoDataForDate(f"Sem dados de {source} para a data de referência.")
    return value, normal


def rain_signal(series: pd.Series, normal_series: pd.Series, normal_years: Iterable[int],
                reference: date, cfg: RainConfig, source: str) -> Signal:
    days = cfg.window_days
    value, normal = _value_and_normal(series, normal_series, normal_years, reference, days,
                                      "sum", source)
    text = {"value": f"{value:.1f}", "days": days, "normal": f"{normal:.1f}"}
    if normal < cfg.min_normal_mm:  # período normalmente seco: percentual não faz sentido
        deficit = normal - value
        if deficit >= cfg.abs_deficit_mm.red:
            color = "red"
        elif deficit >= cfg.abs_deficit_mm.yellow:
            color = "yellow"
        else:
            color = "green"
        key = "rain.dry_season" if color == "green" else f"rain.{color}"
        message = render(key, deviation=f"{deficit:.0f} mm", **text)
        deviation = None
    else:
        deviation = round((value - normal) / normal * 100, 1)
        color = classify(deviation, cfg.pct)
        message = render(f"rain.{color}", deviation=f"{abs(deviation):.0f}%", **text)
    return Signal(kind="rain", color=color, value=round(value, 1), normal=round(normal, 1),
                  deviation_pct=deviation, unit="mm", window_days=days, source=source,
                  message=message)


def soil_signal(series: pd.Series, normal_series: pd.Series, normal_years: Iterable[int],
                reference: date, cfg: SoilMoistureConfig, source: str, unit: str = "1") -> Signal:
    days = cfg.window_days
    value, normal = _value_and_normal(series, normal_series, normal_years, reference, days,
                                      "mean", source)
    if normal > 0:
        deviation = round((value - normal) / normal * 100, 1)
        color = classify(deviation, cfg.pct)
    else:
        deviation, color = None, "green"
    message = render(
        f"soil_moisture.{color}", value=f"{value * 100:.0f}%", normal=f"{normal * 100:.0f}%",
        deviation=f"{abs(deviation or 0):.0f}%",
    )
    return Signal(kind="soil_moisture", color=color, value=round(value, 3),
                  normal=round(normal, 3), deviation_pct=deviation, unit=unit,
                  window_days=days, source=source, message=message)


def _satellite_series(rasters: RasterStore | None, layer: str, shape, reference: date,
                      days: int, agg: str, min_years: int):
    """(série, anos normais) do satélite, se ele cobre a janela de referência e tem histórico
    suficiente (>= min_years anos com a mesma janela, fora do ano de referência); senão None."""
    if rasters is None:
        return None
    series = rasters.plot_series(layer, shape)
    if series is None or series.dropna().empty:
        return None
    if (series.index.min().date() > reference - timedelta(days=days - 1)
            or series.index.max().date() < reference):
        return None
    if climatology.window(series, reference, days, agg) is None:
        return None  # buraco no satélite na janela de referência: o POWER cobre
    candidates = range(series.index.min().year, series.index.max().year + 1)
    years = [y for y in candidates if y != reference.year and climatology.window(
        series, climatology.same_day_in(reference, y), days, agg) is not None]
    return (series, years) if len(years) >= min_years else None


def build_signals(plot: Plot, reference_date: date | None, power: PowerClient,
                  rasters: RasterStore | None = None) -> SignalsResponse:
    cfg = get_config().signals
    lon, lat = plot.centroid
    data = pd.concat([power.history(lat, lon), power.recent(lat, lon)])
    data = data[~data.index.duplicated(keep="last")].sort_index()
    limit = min(last_available_date(data, "PRECTOTCORR"), last_available_date(data, "GWETROOT"))
    adjusted = reference_date is not None and reference_date > limit
    reference = limit if reference_date is None or adjusted else reference_date
    try:
        shape = geometry.to_shape(plot.geometry)
        years = climatology.NORMAL_YEARS

        sat = _satellite_series(rasters, "precipitation", shape, reference, cfg.rain.window_days,
                                "sum", cfg.min_satellite_years)
        if sat:
            rain = rain_signal(sat[0], sat[0], sat[1], reference, cfg.rain,
                               rasters.meta("precipitation")["source"])
        else:
            rain = rain_signal(data["PRECTOTCORR"], data["PRECTOTCORR"], years, reference, cfg.rain,
                               POWER)

        sat = _satellite_series(rasters, "soil_moisture", shape, reference,
                                cfg.soil_moisture.window_days, "mean", cfg.min_satellite_years)
        if sat:
            meta = rasters.meta("soil_moisture")
            soil = soil_signal(sat[0], sat[0], sat[1], reference, cfg.soil_moisture, meta["source"],
                               unit=meta["units"])
        else:
            soil = soil_signal(data["GWETROOT"], data["GWETROOT"], years, reference,
                               cfg.soil_moisture, POWER)
    except NoDataForDate as exc:
        recent_from = power.recent(lat, lon).index.min().date()
        raise NoDataForDate(
            f"{exc} Datas com dado: {HISTORY_START} a {HISTORY_END} e de {recent_from} a {limit}."
        ) from exc
    return SignalsResponse(plot_id=plot.id, reference_date=reference,
                           reference_date_adjusted=adjusted, signals=[rain, soil])
