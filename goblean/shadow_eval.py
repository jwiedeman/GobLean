"""Shadow evaluation utilities for specs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .report import metrics_from_canonical


def shadow_eval(canonical: Path) -> Dict[str, Any]:
    """Return coverage and false positive rate for baseline data."""
    metrics = metrics_from_canonical(canonical)
    coverage = 1.0 if metrics["count"] > 0 else 0.0
    fp_rate = 0.0 if metrics["non_decreasing_playhead"] else 1.0
    result: Dict[str, Any] = {"coverage": coverage, "fp_rate": fp_rate}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run shadow evaluation for the playhead monotonicity rule"
    )
    parser.add_argument("canonical", type=Path, help="Input canonical jsonl")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("out/shadow_eval.json"),
        help="Path to write evaluation result JSON",
    )
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = shadow_eval(args.canonical)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(result, f)
    print(json.dumps(result))


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
