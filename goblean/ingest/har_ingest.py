"""Functions for reading HAR files from disk.

These stubs will evolve to parse thousands of HAR logs using
haralyzer and custom parsers.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable


def ingest_folder(folder: Path) -> Iterable[Path]:
    """Yield HAR file paths in *folder*.

    Parameters
    ----------
    folder:
        Directory containing `.har` files.
    """
    for path in folder.glob("*.har"):
        yield path
