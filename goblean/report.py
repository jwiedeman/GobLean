"""Basic metrics derived from canonical envelopes."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from goblean.fingerprint import fingerprint


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
    first_ts = ts_list[0] if ts_list else None
    return {
        "count": count,
        "cadence": cadence,
        "non_decreasing_playhead": non_decreasing_playhead,
        "first_ts": first_ts,
    }


def write_baseline_csvs(canonical: Path, out_dir: Path) -> None:
    """Write baseline observability CSVs to *out_dir*.

    Only ``metrics_daily.csv`` receives a data row; the rest contain headers
    only so future steps can append to them.
    """

    metrics = metrics_from_canonical(canonical)
    out_dir.mkdir(parents=True, exist_ok=True)

    header = ["date","platform","sdk","version_scope","batch","coverage","fp_rate","tp_rate","fn_rate","violations","total_sessions","notes"]
    date_str = ""
    if metrics.get("first_ts") is not None:
        date_str = datetime.fromtimestamp(float(metrics["first_ts"]), tz=timezone.utc).date().isoformat()

    platform = "unknown"
    sdk = "unknown"
    version = "0.0.0-virtual"
    with canonical.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            env = json.loads(line)
            platform, sdk, ver = fingerprint(env)
            version = ".".join(map(str, ver)) if ver else "0.0.0-virtual"
            break

    row = [date_str,platform,sdk,version,"0",0.0,0.0,0.0,0.0,0,1,""]
    with (out_dir / "metrics_daily.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header,row])

    other_files: Dict[str, list[str]] = {
        "violations.csv": ["session_id","event_id","platform","sdk","version_guess","rule_id","fail_code","severity","ts"],
        "coverage.csv": ["session_id","platform","sdk","version_guess","label","confidence","source_lf_ids"],
        "dictionary.csv": ["param","aliases","type","unit","min","max","mean","stdev","stability","presence_map","evidence_examples"],
        "rules_index.csv": ["rule_id","scope_platforms","scope_sdks","version_range","enabled","constitutional_touch","tests_pass","tests_fail","citations","updated_at"],
        "clusters.csv": ["cluster_id","platform_guess","sdk_guess","signature","representative_sessions","n","novelty_score"],
        "sessions_index.csv": ["session_id","platform","sdk","version_guess","first_ts","last_ts","event_count","file_source"],
    }
    for name, head in other_files.items():
        with (out_dir / name).open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(head)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute basic metrics from canonical JSONL"
    )
    parser.add_argument("path", type=Path, help="Input canonical jsonl")
    parser.add_argument("--out", type=Path, help="Output directory for baseline CSVs", default=None)
    args = parser.parse_args()
    metrics = metrics_from_canonical(args.path)
    if args.out:
        write_baseline_csvs(args.path, args.out)
    print(json.dumps(metrics))


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
