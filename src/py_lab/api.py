from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from py_lab.data_pipeline import basic_clean, load_csv, summarize, save_numeric_hist

app = FastAPI(title="py-lab API", version="0.1.0")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/analyze")
def analyze(
  path: str = Query(..., description="Path to the CSV file"),
  hist: Optional[str] = Query(None, description="Numeric column for histogram")
) -> dict:
    csv_path = Path(path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    df = basic_clean(load_csv(csv_path))
    summary = summarize(df)

    result:dict = {
        "rows": summary.rows,
        "cols": summary.cols,
        "columns": summary.columns,
    }

    if hist:
        out = Path("out/api_hist.png")
        save_numeric_hist(df, hist, out)
        result["hist_path"] = str(out)

    return result
