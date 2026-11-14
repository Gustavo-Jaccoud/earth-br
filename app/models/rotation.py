from typing import Annotated, Literal

from pydantic import BaseModel, Field


class RotationRequest(BaseModel):
    options: list[Annotated[list[str], Field(min_length=1, max_length=3)]] = Field(
        min_length=2, max_length=4
    )


class CriterionScore(BaseModel):
    name: Literal["water", "soil", "suitability"]
    score: float | None
    source: str
    detail: str


class RotationOptionResult(BaseModel):
    crops: list[str]
    scores: list[CriterionScore]
    total: float
    rank: int


class RotationResponse(BaseModel):
    plot_id: int
    options: list[RotationOptionResult]
    verdict: str
