from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.rotation import RotationRequest


class ReportSection(BaseModel):
    title: str
    text: str
    data: dict = {}


class ReportSummary(BaseModel):
    id: int
    plot_id: int
    kind: Literal["analysis", "quiz"]
    title: str
    created_at: datetime


class Report(ReportSummary):
    sections: list[ReportSection]


class AnalysisRequest(BaseModel):
    reference_date: date | None = None
    rotation: RotationRequest | None = None
