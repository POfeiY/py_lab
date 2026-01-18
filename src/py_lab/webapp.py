from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from py_lab.data_pipeline import basic_clean,load_csv_bytes, save_numeric_hist, summarize

app = FastAPI(title="py-lab", version="0.1.0")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/summary")
async def summary(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    content = await file.read()
    df = basic_clean(load_csv_bytes(content))
    s = summarize(df)
    return {"rows": s.rows, "cols": s.cols, "columns": s.columns}

@app.post("/hist")
async def hist(column: str, file: UploadFile = File(...)) -> Response:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    content = await file.read()
    df = basic_clean(load_csv_bytes(content))

    if column not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column not found: {column}")

    from io import BytesIO
    import matplotlib.pyplot as plt
    import pandas as pd

    s = pd.to_numeric(df[column], errors="coerce").dropna()

    buf = BytesIO()
    plt.figure()
    plt.hist(s, bins=20)
    plt.title(f"Histogram: {column}")
    plt.xlabel(column)
    plt.ylabel("count")
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()
    png_bytes = buf.getvalue()

    return Response(content=png_bytes, media_type="image/png")
