"""Basic metrics derived from canonical envelopes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def metrics_from_canonical(path: Path) -> Dict[str, Any]:
    """Compute simple metrics from a canonical JSONL file.

    The function returns a mapping with event ``count``, average ``cadence`` in
    the timestamp sequence (seconds between events), and a boolean flag
    ``non_decreasing_playhead`` indicating whether the ``playhead`` parameter is
    monotonic.
    """

    count = 0
    ts_list: list[float] = []
    playheads: list[float] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            env = json.loads(line)
            count += 1
            params = env.get("params", {})
            ts = params.get("ts")
            if ts is not None:
                try:
                    ts_list.append(float(ts))
                except (TypeError, ValueError):
                    pass
            ph = params.get("playhead")
            if ph is not None:
                try:
                    playheads.append(float(ph))
                except (TypeError, ValueError):
                    pass
    cadence = 0.0
    if len(ts_list) > 1:
        cadence = (ts_list[-1] - ts_list[0]) / (len(ts_list) - 1)
    non_decreasing_playhead = (
        all(later >= earlier for earlier, later in zip(playheads, playheads[1:]))
        if playheads
        else True
    )
    return {
        "count": count,
        "cadence": cadence,
        "non_decreasing_playhead": non_decreasing_playhead,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute basic metrics from canonical JSONL"
    )
    parser.add_argument("path", type=Path, help="Input canonical jsonl")
    args = parser.parse_args()
    metrics = metrics_from_canonical(args.path)
    print(json.dumps(metrics))


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
