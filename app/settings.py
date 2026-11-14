import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    return default if value is None else value.lower() not in ("0", "false", "no", "")


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DATA_DIR", "data")))
    var_dir: Path = field(default_factory=lambda: Path(os.environ.get("VAR_DIR", "var")))
    power_live: bool = field(default_factory=lambda: _env_bool("POWER_LIVE", True))
