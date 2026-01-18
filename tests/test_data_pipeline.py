from __future__ import annotations

import json

import pandas as pd

from py_lab.data_pipeline import basic_clean, summarize


def test_basic_clean_drops_empty_and_duplicates() -> None:
    df = pd.DataFrame(
        {
            "age": [28, 28, None],
            "height": [172, 172, None],
            "name": ["Alice", "Alice", None],
        }
    )
    cleaned = basic_clean(df)
    # 去重后只剩 1 行；全空行被删除
    assert cleaned.shape[0] == 1
    assert list(cleaned.columns) == ["age", "height", "name"]


def test_summarize() -> None:
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    s = summarize(df)
    assert s.rows == 2
    assert s.cols == 2
    assert s.columns == ["x", "y"]

def test_summary_json_is_valid() -> None:
    df = pd.DataFrame({"x": [1, 2]})
    s = summarize(df)
    payload = json.loads(s.to_json())
    assert payload["rows"] == 2
    assert payload["cols"] == 1
    assert payload["columns"] == ["x"]
