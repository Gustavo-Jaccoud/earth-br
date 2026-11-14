import json
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Polygon


@dataclass(frozen=True)
class Region:
    name: str
    ibge_code: str
    state_code: str
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat
    rainy_season_months: tuple[int, ...]

    @property
    def center(self) -> tuple[float, float]:
        """(lon, lat) do centro da bbox, arredondado a 3 casas: estável como chave de cache."""
        min_lon, min_lat, max_lon, max_lat = self.bbox
        return round((min_lon + max_lon) / 2, 3), round((min_lat + max_lat) / 2, 3)

    def contains(self, poly: Polygon) -> bool:
        c = poly.centroid
        min_lon, min_lat, max_lon, max_lat = self.bbox
        return min_lon <= c.x <= max_lon and min_lat <= c.y <= max_lat


def load_region(data_dir: Path) -> Region:
    raw = json.loads((Path(data_dir) / "region.json").read_text(encoding="utf-8"))
    return Region(
        name=raw["name"],
        ibge_code=raw["ibge_code"],
        state_code=raw["state_code"],
        bbox=tuple(raw["bbox"]),
        rainy_season_months=tuple(raw["rainy_season_months"]),
    )
