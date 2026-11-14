"""Balanço hídrico simples: chuva histórica do local contra a necessidade de água da cultura."""
import math
from collections.abc import Iterable

import pandas as pd

from app.models.crops import Crop


def et0_hargreaves(tmax: float, tmin: float, tmean: float, ra_mj: float) -> float:
    """Evapotranspiração de referência (mm/dia), método de Hargreaves-Samani.
    `ra_mj` é a radiação extraterrestre (TOA_SW_DWN do POWER, MJ/m²/dia)."""
    return 0.0023 * 0.408 * ra_mj * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.0))


def monthly_climatology(history: pd.DataFrame, years: Iterable[int] = range(2001, 2021)
                        ) -> pd.DataFrame:
    """Chuva e ET0 mensais (mm, totais médios entre os anos), índice = mês 1..12."""
    df = history[history.index.year.isin(list(years))].copy()
    df["et0"] = [
        et0_hargreaves(tmax, tmin, tmean, ra)
        for tmax, tmin, tmean, ra in zip(df["T2M_MAX"], df["T2M_MIN"], df["T2M"],
                                         df["TOA_SW_DWN"], strict=True)
    ]
    monthly = df.groupby([df.index.year, df.index.month])[["PRECTOTCORR", "et0"]].sum()
    mean = monthly.groupby(level=1).mean()
    return mean.rename(columns={"PRECTOTCORR": "rain_mm", "et0": "et0_mm"}).reindex(range(1, 13))


def sequence_months(crops: list[Crop]) -> list[tuple[Crop, int, float]]:
    """(cultura, mês 1..12, kc) para cada mês de cultivo. A 1ª cultura começa no seu mês de
    plantio; cada seguinte, no mês após o fim da anterior (os meses dão a volta em 12)."""
    out: list[tuple[Crop, int, float]] = []
    start = crops[0].planting_month
    for crop in crops:
        for i, kc in enumerate(crop.kc):
            out.append((crop, (start - 1 + i) % 12 + 1, kc))
        start = (start - 1 + len(crop.kc)) % 12 + 1
    return out


def water_score(seq: list[tuple[Crop, int, float]], clim: pd.DataFrame) -> float:
    """0..100: média, nos meses de cultivo, de min(1, chuva / (kc × ET0))."""
    ratios = []
    for _, month, kc in seq:
        demand = kc * clim.loc[month, "et0_mm"]
        ratios.append(1.0 if demand <= 0 else min(1.0, clim.loc[month, "rain_mm"] / demand))
    return 100 * sum(ratios) / len(ratios)
