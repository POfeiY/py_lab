from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


@dataclass(frozen=True)
class Summary:
    rows: int
    cols: int
    columns: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def load_csv(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    return pd.read_csv(p)

def load_csv_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_csv(BytesIO(data))


def basic_clean(df: pd.DataFrame) -> pd.DataFrame:
    # 规则：去掉全空行、去掉重复行、列名去首尾空格
    df = df.dropna(how="all").drop_duplicates()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def summarize(df: pd.DataFrame) -> Summary:
    return Summary(
        rows=int(df.shape[0]),
        cols=int(df.shape[1]),
        columns=[str(c) for c in df.columns],
    )


def save_numeric_hist(df: pd.DataFrame, column: str, out_path: str | Path, bins: int = 20) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    s = pd.to_numeric(df[column], errors="coerce").dropna()

    flg, ax = plt.subplots()
    ax.hist(s, bins=bins)
    ax.set_title(f"Histogram: {column}")
    ax.set_xlabel(column)
    ax.set_ylabel("count")
    flg.tight_layout()
    flg.savefig(out)
    plt.close()
