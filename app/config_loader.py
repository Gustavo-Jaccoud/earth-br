from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.models.crops import Crop

DEFAULT_CONFIG_DIR = Path(__file__).parent / "config"


class Thresholds(BaseModel):
    yellow: float
    red: float


class RainConfig(BaseModel):
    window_days: int
    min_normal_mm: float
    pct: Thresholds
    abs_deficit_mm: Thresholds


class SoilMoistureConfig(BaseModel):
    window_days: int
    pct: Thresholds


class SignalsConfig(BaseModel):
    rain: RainConfig
    soil_moisture: SoilMoistureConfig
    min_satellite_years: int


class RotationConfig(BaseModel):
    weights: dict[str, float]
    ndvi_range: tuple[float, float]
    soil_restoring_bonus: float
    ndvi_years: int


class QuizOptionConfig(BaseModel):
    id: str
    label: str
    risk: int
    suggestion: str | None = None


class QuizQuestionConfig(BaseModel):
    id: str
    text: str
    options: list[QuizOptionConfig]


class QuizConfig(BaseModel):
    questions: list[QuizQuestionConfig]


class AppConfig(BaseModel):
    crops: list[Crop]
    signals: SignalsConfig
    rotation: RotationConfig
    quiz: QuizConfig
    phrases: dict[str, str]


def _read(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(config_dir: Path = DEFAULT_CONFIG_DIR) -> AppConfig:
    return AppConfig(
        crops=_read(config_dir / "crops.yaml")["crops"],
        signals=_read(config_dir / "signals.yaml"),
        rotation=_read(config_dir / "rotation.yaml"),
        quiz=_read(config_dir / "quiz.yaml"),
        phrases=_read(config_dir / "phrases.yaml"),
    )


@lru_cache
def get_config() -> AppConfig:
    return load_config()
