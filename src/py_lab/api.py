from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from py_lab.data_pipeline import basic_clean, load_csv, save_numeric_hist, summarize

app = FastAPI(title="py-lab API", version="0.1.0")

BASE_OUT_DIR = Path("out") / "requests"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
RESULT_TTL_SECONDS = 24 * 3600  # 24 hours

@app.get("/results/{request_id}/summary")
def get_summary(request_id:str) -> JSONResponse:
    p = BASE_OUT_DIR / request_id / "summary.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    return JSONResponse(content=json.loads(p.read_text(encoding="utf-8")))

@app.get("/results/{request_id}/hist.png")
def get_hist(request_id:str) -> FileResponse:
    p = BASE_OUT_DIR / request_id / "hist.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Histogram not found")
    return FileResponse(path=str(p), media_type="image/png", filename="hist.png")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/analyze")
async def analyze_upload(
    file: UploadFile = File(..., description="CSV file to analyze"),
    hist: str | None = Form(None, description="Numeric column for histogram")
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=404, detail="Only CSV files are supported")

    req_id = uuid.uuid4().hex[:12]
    work_dir = Path("out") / "requests" / req_id
    work_dir.mkdir(parents=True, exist_ok=True)

    csv_path = work_dir / "input.csv"
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large(max 10MB)")
    csv_path.write_bytes(content)

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
        result["hist_url"] = f"/results/{req_id}/hist.png"

    (work_dir / "summary.json").write_text(summary.to_json(), encoding="utf-8")
    result["summary_url"] = f"/results/{req_id}/summary"

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

@app.post("/admin/cleanup")
def admin_cleanup() -> dict[str, int]:
    removed = cleanup_expired_requests(BASE_OUT_DIR, RESULT_TTL_SECONDS)
    return {"removed": removed}
