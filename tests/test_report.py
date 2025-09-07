import json
from pathlib import Path

from goblean.report import metrics_from_canonical


def test_metrics_from_canonical(tmp_path: Path) -> None:
    data = [
        {"params": {"ts": 0, "playhead": 0}},
        {"params": {"ts": 1, "playhead": 1}},
        {"params": {"ts": 2, "playhead": 2}},
    ]
    path = tmp_path / "canonical.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for env in data:
            f.write(json.dumps(env) + "\n")
    metrics = metrics_from_canonical(path)
    assert metrics["count"] == 3
    assert metrics["cadence"] == 1.0
    assert metrics["non_decreasing_playhead"] is True
