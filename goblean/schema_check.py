"""Validate canonical envelopes against a simple schema."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel


class CanonicalEnvelope(BaseModel):
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Dict[str, Any]
    params: Dict[str, Any]
    body: Optional[str] = None
    form: Optional[Dict[str, str]] = None
    json: Any | None = None


def validate_envelope(envelope: Dict[str, Any]) -> CanonicalEnvelope:
    """Return a validated ``CanonicalEnvelope`` instance."""
    return CanonicalEnvelope.model_validate(envelope)


def validate_file(path: Path) -> int:
    """Validate each line of *path* and return the number of envelopes."""
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            validate_envelope(json.loads(line))
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate canonical JSONL file")
    parser.add_argument("path", type=Path, help="Input canonical jsonl")
    args = parser.parse_args()

    count = validate_file(args.path)
    print(f"Validated {count} envelopes")


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
