"""Sanity tests for package imports."""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import goblean


def test_import() -> None:
    assert hasattr(goblean, "ingest")
