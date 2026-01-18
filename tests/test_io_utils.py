from __future__ import annotations

from pathlib import Path

from py_lab.io_utils import read_text


def test_read_text(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    assert read_text(f) == "hello world"
