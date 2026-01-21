from __future__ import annotations

import json
import logging
import secrets
import shutil
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from py_lab.data_pipeline import basic_clean, load_csv, save_numeric_hist, summarize
from py_lab.logging_utils import RequestIdFilter, setup_logging
from py_lab.schemas import AnalyzeResponse, CleanupResponse, ErrorResponse, SummaryModel
from py_lab.settings import settings
from py_lab.signing import constant_time_eq, sign

app = FastAPI(title="py-lab API", version="0.1.0")

RESULTS_DIR = Path(settings.out_dir) / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/results",
    StaticFiles(directory=str(RESULTS_DIR)),
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

def _required_valid_signature(request_id:str, filename:str, exp:int,signature:str) -> None:
    if not settings.download_signing_key:
        return # 未启用签名，开发模式

    now = int(time.time())
    if exp < now:
        raise HTTPException(status_code=403, detail="URL has expired")

    message = f"{request_id}:{filename}:{exp}"
    expected = sign(settings.download_signing_key, message)
    if not constant_time_eq(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

def make_download_url(req_id:str, filename:str) -> str:
    exp = int(time.time()) + settings.download_url_ttl_seconds
    if not settings.download_signing_key:
        # 开发模式返回静态连接
        return absolute_url(f"/results/{req_id}/{filename}")

    message = f"{req_id}:{filename}:{exp}"
    sig = sign(settings.download_signing_key, message)
    return absolute_url(f"/download/{req_id}/{filename}?exp={exp}&sig={sig}")

@app.api_route(
    "/download/{request_id}/{filename}",
    methods=["GET", "HEAD"],
    responses={
        200: {"content": {"image/png": {}}, "description": "File Download"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "File Not Found"}
    },
)
def download_file(request_id:str, filename:str, exp: int = Query(...), sig: str = Query(...)):
    if filename not in ('hist.png', 'summary.json'):
        raise HTTPException(status_code=404, detail="File not found with suffix")

    _required_valid_signature(request_id, filename, exp, sig)

    p = BASE_OUT_DIR / request_id / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {p}")

    media_type = "image/png" if filename.endswith(".png") else "application/json"
    return FileResponse(path=str(p), media_type=media_type, filename=filename)

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

    req_id = secrets.token_urlsafe(24)

    req_logger = logging.getLogger("py_lab.api.request")
    req_logger.addFilter(RequestIdFilter(req_id))
    req_logger.info("request received: filename=%s", file.filename)

    work_dir = Path(settings.out_dir) / "requests" / req_id
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
        result["hist_url"] = make_download_url(req_id, "hist.png")

    (work_dir / "summary.json").write_text(summary.to_json(), encoding="utf-8")
    req_logger.info("summary: rows=%d cols=%d", summary.rows, summary.cols)

    result["summary_url"] = make_download_url(req_id, "summary.json")

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
