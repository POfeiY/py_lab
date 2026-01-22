from __future__ import annotations

from pydantic import BaseModel, Field


class SummaryModel(BaseModel):
    rows: int = Field(..., ge=0)
    cols: int = Field(..., ge=0)
    columns: list[str]

class AnalyzeResponse(BaseModel):
    request_id: str
    summary: SummaryModel
    hist_url: str | None = None
    summary_url: str

    anomaly: AnomalyModel | None = None

class ErrorResponse(BaseModel):
    detail: str

class CleanupResponse(BaseModel):
    removed: int = Field(..., ge=0)

class AnomalyModel(BaseModel):
    indices: list[int]
    scores: list[float]
    top_rows: list[AnomalyRowPreview] = []

class AnomalyRowPreview(BaseModel):
    index: int
    score: float
    row: dict[str, str | float | int | None]
