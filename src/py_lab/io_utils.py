from __future__ import annotations

from pathlib import Path


def read_text(path: str | Path, encoding: str = 'utf-8') -> str:
    """Read text file and return its content.

    Args:
        path (str | Path): The path to the file.
        encoding (str, optional): The encoding to use. Defaults to 'utf-8'.

    Returns:
        str: The content of the file.
    """
    p = Path(path)
    return p.read_text(encoding=encoding)
