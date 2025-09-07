import json
from pathlib import Path

from goblean.normalize.__main__ import normalize_entries
from goblean.report import metrics_from_canonical


def test_playhead_monotonicity_pass(tmp_path: Path) -> None:
    har_path = Path("rules/tests/HB_PLAYHEAD_MONOTONIC_WEB__pass__simple.har")
    har = json.loads(har_path.read_text())
    canonical = tmp_path / "canonical.jsonl"
    with canonical.open("w", encoding="utf-8") as out:
        for env in normalize_entries(har):
            out.write(json.dumps(env) + "\n")
    metrics = metrics_from_canonical(canonical)
    assert metrics["non_decreasing_playhead"] is True
