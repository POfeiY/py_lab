from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from py_lab.data_pipeline import basic_clean, load_csv, save_numeric_hist, summarize
from py_lab.logging_utils import RequestIdFilter, setup_logging
from py_lab.schemas import AnalyzeResponse, CleanupResponse, ErrorResponse, SummaryModel
from py_lab.settings import settings

app = FastAPI(title="py-lab API", version="0.1.0")
app.mount(
    "/results",
    StaticFiles(directory=str(Path(settings.out_dir) / "results")),
    name="results")
setup_logging(settings.log_level)
logger = logging.getLogger("py_lab.api")

BASE_OUT_DIR = Path(settings.out_dir) / "requests"
MAX_BYTES = settings.max_bytes  # 10 MB
RESULT_TTL_SECONDS = settings.result_ttl_seconds  # 24 hours

def absolute_url(path:str) -> str:
    if not settings.base_url:
        return path
    return settings.base_url.rstrip("/") + path

@app.get(
    "/results/{request_id}/summary.json",
    response_model=SummaryModel,
    responses={404: {"model": ErrorResponse, "description": "Result Not Found"}},)
def get_summary(request_id:str) -> JSONResponse:
    p = BASE_OUT_DIR / request_id / "summary.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    return JSONResponse(content=json.loads(p.read_text(encoding="utf-8")))

@app.get(
    "/results/{request_id}/hist.png",
    responses={
        200: {"content": {"image/png": {}}, "description": "Histogram PNG"},
        404: {"model": ErrorResponse, "description": "Histogram Not Found"}},)
def get_hist(request_id:str) -> FileResponse:
    p = BASE_OUT_DIR / request_id / "hist.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Histogram not found")
    return FileResponse(path=str(p), media_type="image/png", filename="hist.png")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        413: {"model": ErrorResponse, "description": "Payload Too Large"}},)
async def analyze_upload(
    file: UploadFile = File(..., description="CSV file to analyze"),
    hist: str | None = Form(None, description="Numeric column for histogram")
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=404, detail="Only CSV files are supported")

    req_id = uuid.uuid4().hex[:12]

    req_logger = logging.getLogger("py_lab.api.request")
    req_logger.addFilter(RequestIdFilter(req_id))
    req_logger.info("request received: filename=%s", file.filename)

    work_dir = Path(settings.out_dir) / "results" / req_id
    work_dir.mkdir(parents=True, exist_ok=True)

    csv_path = work_dir / "input.csv"
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large(max 10MB)")
    csv_path.write_bytes(content)
    req_logger.info("saved input: %s (%d bytes)", csv_path, len(content))

    df = basic_clean(load_csv(csv_path))
    summary = summarize(df)

    result:dict = {
        "request_id": req_id,
        "summary": {
            "rows": summary.rows,
            "cols": summary.cols,
            "columns": summary.columns,
        },
    }

    if hist:
        png_path = work_dir / "hist.png"
        save_numeric_hist(df, hist, png_path)
        result["hist_url"] = absolute_url(f"/results/{req_id}/hist.png")

    (work_dir / "summary.json").write_text(summary.to_json(), encoding="utf-8")
    req_logger.info("summary: rows=%d cols=%d", summary.rows, summary.cols)

    result["summary_url"] = absolute_url(f"/results/{req_id}/summary.json")

    return result

def cleanup_expired_requests(base_dir:Path,ttl_seconds:int) -> int:
    now = time.time()
    removed = 0

    if not base_dir.exists():
        return 0

    for subdir in base_dir.iterdir():
        if not subdir.is_dir():
            continue
        try:
            mtime = subdir.stat().st_mtime
        except FileNotFoundError:
            continue

        if now - mtime > ttl_seconds:
            shutil.rmtree(subdir, ignore_errors=True)
            removed += 1

    return removed

@app.post(
    "/admin/cleanup",
    response_model=CleanupResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },)
def admin_cleanup(x_admin_token: str | None = Header(default = None)) -> dict[str, int]:
    if settings.admin_token:
        if not x_admin_token or x_admin_token != settings.admin_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

    removed = cleanup_expired_requests(BASE_OUT_DIR, RESULT_TTL_SECONDS)
    return {"removed": removed}
