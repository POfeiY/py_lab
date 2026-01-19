from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from py_lab.data_pipeline import basic_clean, load_csv, save_numeric_hist, summarize

app = FastAPI(title="py-lab API", version="0.1.0")

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
    content = await file.read()
    csv_path.write_bytes(content)

    df = basic_clean(load_csv(csv_path))
    summary = summarize(df)

    result:dict = {
        "request_id": req_id,
        "rows": summary.rows,
        "cols": summary.cols,
        "columns": summary.columns,
    }

    if hist:
        png_path = work_dir / "hist.png"
        save_numeric_hist(df, hist, png_path)
        result["hist_path"] = str(png_path)

    (work_dir / "summary.json").write_text(summary.to_json(), encoding="utf-8")
    result["summary_path"] = str(work_dir / "summary.json")

    return result
