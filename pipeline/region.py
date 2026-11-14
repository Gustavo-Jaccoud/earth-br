import json
from pathlib import Path

DEFAULT_PATH = Path("data/region.json")


def load_bbox(path: Path = DEFAULT_PATH) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) da região de demonstração."""
    return tuple(json.loads(Path(path).read_text(encoding="utf-8"))["bbox"])
