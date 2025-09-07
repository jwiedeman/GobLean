"""Functions for reading HAR files from disk.

These stubs will evolve to parse thousands of HAR logs using
haralyzer and custom parsers.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Iterable


def read_har(path: Path) -> Dict[str, Any]:
    """Return parsed HAR JSON from *path*.

    Parameters
    ----------
    path:
        Path to a ``.har`` file.
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ingest_folder(folder: Path) -> Iterable[Dict[str, Any]]:
    """Yield parsed HAR data for files in *folder*.

    Parameters
    ----------
    folder:
        Directory containing ``.har`` files.
    """
    for path in folder.glob("*.har"):
        yield read_har(path)
