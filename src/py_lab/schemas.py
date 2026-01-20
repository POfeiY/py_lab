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

class ErrorResponse(BaseModel):
    detail: str

class CleanupResponse(BaseModel):
    removed: int = Field(..., ge=0)
