"""Cliente da NASA POWER (série diária por ponto) com cache em disco.

O cache permite a demo funcionar sem internet: respostas brutas ficam em
`{cache_dir}/{kind}_{lat:.2f}_{lon:.2f}.json` e podem ser versionadas.
"""
import json
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "GWETROOT",
                "ALLSKY_SFC_SW_DWN", "TOA_SW_DWN"]
POWER_UNITS = {"T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "PRECTOTCORR": "mm/day", "RH2M": "%",
               "GWETROOT": "1", "ALLSKY_SFC_SW_DWN": "MJ/m^2/day", "TOA_SW_DWN": "MJ/m^2/day"}
HISTORY_START = date(2001, 1, 1)
HISTORY_END = date(2023, 12, 31)
RECENT_DAYS = 400
# Grade nativa do POWER para o que usamos (MERRA-2): 0,5° de latitude x 0,625° de longitude.
# Pontos na mesma célula recebem exatamente os mesmos números (conferido na API).
GRID_LAT, GRID_LON = 0.5, 0.625
RECENT_TTL = timedelta(hours=6)  # cache do "recent" mais novo que isto dispensa a rede
HISTORY_TIMEOUT = httpx.Timeout(60.0)
RECENT_TIMEOUT = httpx.Timeout(10.0, connect=3.0)  # rede ruim não pode travar a demo
FILL_VALUE = -999.0

UNAVAILABLE_MESSAGE = (
    "NASA POWER data could not be fetched right now and there is no saved data for this location."
)


class PowerUnavailable(Exception):
    def __init__(self, message: str = UNAVAILABLE_MESSAGE):
        super().__init__(message)


def last_available_date(df: pd.DataFrame, column: str) -> date:
    valid = df[column].dropna()
    if valid.empty:
        raise PowerUnavailable("NASA POWER has no data yet for this location and period.")
    return valid.index[-1].date()


def _to_frame(raw: dict) -> pd.DataFrame:
    params = raw["properties"]["parameter"]
    df = pd.DataFrame({p: pd.Series(params.get(p, {})) for p in POWER_PARAMS})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.sort_index().replace(FILL_VALUE, float("nan"))


def grid_cell(lat: float, lon: float) -> tuple[float, float]:
    """Centro da célula da grade do POWER que contém o ponto."""
    return round(lat / GRID_LAT) * GRID_LAT, round(lon / GRID_LON) * GRID_LON


class PowerClient:
    def __init__(
        self,
        cache_dir: Path,
        live: bool = True,
        http: httpx.Client | None = None,
        today: Callable[[], date] = date.today,
        recent_ttl: timedelta = RECENT_TTL,
    ):
        self.cache_dir = Path(cache_dir)
        self.live = live
        self._http = http
        self.today = today
        self.recent_ttl = recent_ttl

    def cache_path(self, kind: str, lat: float, lon: float) -> Path:
        lat, lon = grid_cell(lat, lon)
        return self.cache_dir / f"{kind}_{lat:.3f}_{lon:.3f}.json"

    def history(self, lat: float, lon: float) -> pd.DataFrame:
        """2001-01-01..2023-12-31. Se há cache, nunca vai à rede."""
        path = self.cache_path("history", lat, lon)
        if path.exists():
            return _to_frame(json.loads(path.read_text()))
        if self.live:
            try:
                raw = self._fetch_and_cache(path, lat, lon, HISTORY_START, HISTORY_END,
                                            HISTORY_TIMEOUT)
                return _to_frame(raw)
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        raise PowerUnavailable()

    def recent(self, lat: float, lon: float) -> pd.DataFrame:
        """Últimos 400 dias. Cache recente (< 6 h) é usado direto; senão tenta ao vivo, com
        timeout curto, e se falhar usa o cache (mesmo velho)."""
        path = self.cache_path("recent", lat, lon)
        if self.live and not self._is_fresh(path):
            end = self.today()
            try:
                raw = self._fetch_and_cache(path, lat, lon, end - timedelta(days=RECENT_DAYS), end,
                                            RECENT_TIMEOUT)
                return _to_frame(raw)
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        if path.exists():
            return _to_frame(json.loads(path.read_text()))
        raise PowerUnavailable()

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        return time.time() - path.stat().st_mtime < self.recent_ttl.total_seconds()

    def _fetch_and_cache(self, path: Path, lat: float, lon: float, start: date, end: date,
                         timeout: httpx.Timeout) -> dict:
        if self._http is None:
            self._http = httpx.Client()  # um só cliente, reaproveitado entre as chamadas
        lat, lon = grid_cell(lat, lon)
        response = self._http.get(POWER_URL, timeout=timeout, params={
            "parameters": ",".join(POWER_PARAMS),
            "community": "AG",
            "longitude": f"{lon:.3f}",
            "latitude": f"{lat:.3f}",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        })
        response.raise_for_status()
        raw = response.json()
        _to_frame(raw)  # valida o formato antes de gravar
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(raw))
        except OSError:
            pass  # disco somente leitura (hospedagem): segue com o dado em memória, sem cache
        return raw
