"""Cliente da NASA POWER (série diária por ponto) com cache em disco.

O cache permite a demo funcionar sem internet: respostas brutas ficam em
`{cache_dir}/{kind}_{lat:.2f}_{lon:.2f}.json` e podem ser versionadas.
"""
import json
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
FILL_VALUE = -999.0

UNAVAILABLE_MESSAGE = (
    "Não foi possível obter dados da NASA POWER agora e não há dados salvos para este local."
)


class PowerUnavailable(Exception):
    def __init__(self, message: str = UNAVAILABLE_MESSAGE):
        super().__init__(message)


def last_available_date(df: pd.DataFrame, column: str) -> date:
    valid = df[column].dropna()
    if valid.empty:
        raise PowerUnavailable("A NASA POWER ainda não tem dados para este local e período.")
    return valid.index[-1].date()


def _to_frame(raw: dict) -> pd.DataFrame:
    params = raw["properties"]["parameter"]
    df = pd.DataFrame({p: pd.Series(params.get(p, {})) for p in POWER_PARAMS})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.sort_index().replace(FILL_VALUE, float("nan"))


class PowerClient:
    def __init__(
        self,
        cache_dir: Path,
        live: bool = True,
        http: httpx.Client | None = None,
        today: Callable[[], date] = date.today,
    ):
        self.cache_dir = Path(cache_dir)
        self.live = live
        self._http = http
        self.today = today

    def cache_path(self, kind: str, lat: float, lon: float) -> Path:
        return self.cache_dir / f"{kind}_{lat:.2f}_{lon:.2f}.json"

    def history(self, lat: float, lon: float) -> pd.DataFrame:
        """2001-01-01..2023-12-31. Se há cache, nunca vai à rede."""
        path = self.cache_path("history", lat, lon)
        if path.exists():
            return _to_frame(json.loads(path.read_text()))
        if self.live:
            try:
                return _to_frame(self._fetch_and_cache(path, lat, lon, HISTORY_START, HISTORY_END))
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        raise PowerUnavailable()

    def recent(self, lat: float, lon: float) -> pd.DataFrame:
        """Últimos 400 dias. Tenta ao vivo; se falhar, usa o cache."""
        path = self.cache_path("recent", lat, lon)
        if self.live:
            end = self.today()
            try:
                raw = self._fetch_and_cache(path, lat, lon, end - timedelta(days=RECENT_DAYS), end)
                return _to_frame(raw)
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        if path.exists():
            return _to_frame(json.loads(path.read_text()))
        raise PowerUnavailable()

    def _fetch_and_cache(self, path: Path, lat: float, lon: float, start: date, end: date) -> dict:
        http = self._http or httpx.Client(timeout=60)
        response = http.get(POWER_URL, params={
            "parameters": ",".join(POWER_PARAMS),
            "community": "AG",
            "longitude": f"{lon:.2f}",
            "latitude": f"{lat:.2f}",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        })
        response.raise_for_status()
        raw = response.json()
        _to_frame(raw)  # valida o formato antes de gravar
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw))
        return raw
