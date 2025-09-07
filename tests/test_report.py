import csv
import json
from pathlib import Path

from goblean.report import metrics_from_canonical, write_baseline_csvs


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


def test_write_baseline_csvs(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.jsonl"
    with canonical.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"params": {"ts": 0, "playhead": 0}}) + "\n")
    doc_cache_path = Path("docs/doc_cache.json")
    doc_cache_path.parent.mkdir(exist_ok=True)
    original = doc_cache_path.read_text(encoding="utf-8") if doc_cache_path.exists() else None
    with doc_cache_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "cached://docs/playhead-monotonicity": {
                    "source_url": "https://example.com/playhead-monotonicity",
                    "first_seen": "2024-01-01T00:00:00Z",
                    "last_verified": "2024-01-01T00:00:00Z",
                }
            },
            f,
        )
    with doc_cache_path.open("r", encoding="utf-8") as f:
        cache_before = json.load(f)
    prev_last_verified = cache_before["cached://docs/playhead-monotonicity"]["last_verified"]
    out_dir = tmp_path / "out"
    write_baseline_csvs(canonical, out_dir)
    with doc_cache_path.open("r", encoding="utf-8") as f:
        cache_after = json.load(f)
    new_last_verified = cache_after["cached://docs/playhead-monotonicity"]["last_verified"]
    assert new_last_verified != prev_last_verified
    metrics_path = out_dir / "metrics_daily.csv"
    rows = list(csv.reader(metrics_path.open("r", encoding="utf-8")))
    assert rows[0] == ["date","platform","sdk","version_scope","batch","coverage","fp_rate","tp_rate","fn_rate","violations","total_sessions","notes"]
    assert rows[1][0] == "1970-01-01"
    expected_headers = {
        "violations.csv": ["session_id","event_id","platform","sdk","version_guess","rule_id","fail_code","severity","ts"],
        "coverage.csv": ["session_id","platform","sdk","version_guess","label","confidence","source_lf_ids"],
        "dictionary.csv": ["param","aliases","type","unit","min","max","mean","stdev","stability","presence_map","evidence_examples"],
        "clusters.csv": ["cluster_id","platform_guess","sdk_guess","signature","representative_sessions","n","novelty_score"],
        "sessions_index.csv": ["session_id","platform","sdk","version_guess","first_ts","last_ts","event_count","file_source"],
    }
    for name, header in expected_headers.items():
        with (out_dir / name).open("r", encoding="utf-8") as f:
            assert next(csv.reader(f)) == header
    rules_rows = list(csv.reader((out_dir / "rules_index.csv").open("r", encoding="utf-8")))
    assert rules_rows[0] == [
        "rule_id",
        "scope_platforms",
        "scope_sdks",
        "version_range",
        "enabled",
        "constitutional_touch",
        "tests_pass",
        "tests_fail",
        "citations",
        "citation_quotes",
        "citation_source_urls",
        "citation_first_seen",
        "citation_last_verified",
        "updated_at",
    ]
    assert rules_rows[1][0] == "HB_PLAYHEAD_MONOTONIC_WEB"
    assert rules_rows[1][3] == "0.0.0-virtual"
    assert rules_rows[1][6] == "1"
    assert rules_rows[1][7] == "0"
    assert rules_rows[1][9] == "Playhead must not decrease."
    assert rules_rows[1][10] == "https://example.com/playhead-monotonicity"
    assert rules_rows[1][11] == "2024-01-01T00:00:00Z"
    assert rules_rows[1][12] == new_last_verified
    if original is None:
        doc_cache_path.unlink()
    else:
        doc_cache_path.write_text(original, encoding="utf-8")


def test_write_baseline_csvs_backfills_doc_cache(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.jsonl"
    with canonical.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"params": {"ts": 0, "playhead": 0}}) + "\n")
    doc_cache_path = Path("docs/doc_cache.json")
    doc_cache_path.parent.mkdir(exist_ok=True)
    original = doc_cache_path.read_text(encoding="utf-8") if doc_cache_path.exists() else None
    if doc_cache_path.exists():
        doc_cache_path.unlink()
    out_dir = tmp_path / "out"
    write_baseline_csvs(canonical, out_dir)
    assert doc_cache_path.exists()
    with doc_cache_path.open("r", encoding="utf-8") as f:
        cache = json.load(f)
    entry = cache["cached://docs/playhead-monotonicity"]
    assert entry["first_seen"]
    assert entry["last_verified"]
    if original is None:
        doc_cache_path.unlink()
    else:
        doc_cache_path.write_text(original, encoding="utf-8")
