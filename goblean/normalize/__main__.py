"""CLI for converting HAR entries to canonical JSONL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable

from .envelope import canonical_envelope


def normalize_entries(har: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield canonical envelopes for each entry in *har*.

    The function expects a mapping parsed from a HAR file.
    """
    entries = har.get("log", {}).get("entries", [])
    for entry in entries:
        yield canonical_envelope(entry)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write canonical JSONL from HAR file."
    )
    parser.add_argument("har", type=Path, help="Input .har file")
    parser.add_argument("out", type=Path, help="Output .jsonl path")
    args = parser.parse_args()

    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out_f:
        for env in normalize_entries(har):
            out_f.write(json.dumps(env) + "\n")


if __name__ == "__main__":
    main()
