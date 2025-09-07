"""Basic metrics derived from canonical envelopes."""
from __future__ import annotations

import argparse
import csv
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import urllib.request

from goblean.fingerprint import fingerprint


def populate_rules_index(out_dir: Path) -> None:
    """Populate ``rules_index.csv`` with scope and test counts."""

    specs_dir = Path("rules/specs")
    tests_dir = Path("rules/tests")
    doc_cache_path = Path("docs/doc_cache.json")
    doc_cache_path.parent.mkdir(parents=True, exist_ok=True)
    doc_cache: Dict[str, Dict[str, Any]] = {}
    if doc_cache_path.exists():
        with doc_cache_path.open("r", encoding="utf-8") as f:
            doc_cache = json.load(f)
    unreachable_entries: list[list[str]] = []
    header = [
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
    rows = []
    for spec_file in specs_dir.glob("*.yaml"):
        with spec_file.open("r", encoding="utf-8") as f:
            spec = json.load(f)
        scope = spec.get("scope", {})
        checks = spec.get("checks", [])
        constitutional_touch = ""
        for check in checks:
            if check.get("non_decreasing_playhead"):
                constitutional_touch = "non_decreasing_playhead"
                break
        rule_id = spec.get("rule_id", "")
        platforms = "|".join(scope.get("platforms", []))
        sdks = "|".join(scope.get("sdks", []))
        version_range = scope.get("version_range", "")
        tests_pass = len(list(tests_dir.glob(f"{rule_id}__pass__*.har")))
        tests_fail = len(list(tests_dir.glob(f"{rule_id}__fail__*.har")))
        citation_urls: list[str] = []
        citation_quotes: list[str] = []
        citation_source_urls: list[str] = []
        citation_first_seen: list[str] = []
        citation_last_verified: list[str] = []
        for c in spec.get("citations", []):
            url = c.get("url", "")
            if not url:
                continue
            now = datetime.now(timezone.utc).isoformat()
            entry = doc_cache.get(url)
            if entry:
                reachable = entry.get("reachable", True)
                if not reachable:
                    unreachable_entries.append(
                        [
                            url,
                            entry.get("source_url", ""),
                            entry.get("first_seen", ""),
                            entry.get("last_verified", ""),
                        ]
                    )
                    continue
                entry["last_verified"] = now
                doc_cache[url] = entry
                citation_source_urls.append(entry.get("source_url", ""))
                citation_first_seen.append(entry.get("first_seen", ""))
                citation_last_verified.append(entry.get("last_verified", ""))
            else:
                entry = {
                    "source_url": c.get("source_url", ""),
                    "first_seen": now,
                    "last_verified": now,
                    "reachable": True,
                }
                doc_cache[url] = entry
                citation_source_urls.append(entry["source_url"])
                citation_first_seen.append(entry["first_seen"])
                citation_last_verified.append(entry["last_verified"])
            citation_urls.append(url)
            citation_quotes.append(c.get("quote", ""))
        citations = "|".join(citation_urls)
        citation_quotes_str = "|".join(citation_quotes)
        citation_source_urls_str = "|".join([s for s in citation_source_urls if s])
        citation_first_seen_str = "|".join([s for s in citation_first_seen if s])
        citation_last_verified_str = "|".join([s for s in citation_last_verified if s])
        updated_at = datetime.now(timezone.utc).isoformat()
        rows.append(
            [
                rule_id,
                platforms,
                sdks,
                version_range,
                "true",
                constitutional_touch,
                str(tests_pass),
                str(tests_fail),
                citations,
                citation_quotes_str,
                citation_source_urls_str,
                citation_first_seen_str,
                citation_last_verified_str,
                updated_at,
            ]
        )
    with doc_cache_path.open("w", encoding="utf-8") as f:
        json.dump(doc_cache, f, indent=2)
    with (out_dir / "rules_index.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    with (out_dir / "unreachable_docs.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["citation_url", "source_url", "first_seen", "last_verified"])
        writer.writerows(unreachable_entries)


def verify_doc_cache(doc_cache_path: Path | None = None) -> Dict[str, bool]:
    """Verify cached documents and update ``last_verified`` timestamps.

    Performs a ``HEAD`` request against each ``source_url``. Entries that
    respond with a status code < 400 are marked ``reachable`` and have their
    ``last_verified`` field refreshed to the current time. Unreachable entries
    are marked ``reachable`` = ``False`` and retain their previous timestamps.
    The function returns a mapping from citation URLs to a boolean indicating
    verification success.
    """

    if doc_cache_path is None:
        doc_cache_path = Path("docs/doc_cache.json")
    doc_cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache: Dict[str, Dict[str, Any]] = {}
    if doc_cache_path.exists():
        with doc_cache_path.open("r", encoding="utf-8") as f:
            cache = json.load(f)
    results: Dict[str, bool] = {}
    for url, entry in cache.items():
        source = entry.get("source_url", "")
        ok = False
        if source:
            try:
                req = urllib.request.Request(source, method="HEAD")
                with urllib.request.urlopen(req) as resp:
                    ok = resp.status < 400
            except Exception:
                ok = False
        entry["reachable"] = ok
        if ok:
            entry["last_verified"] = datetime.now(timezone.utc).isoformat()
        results[url] = ok
        cache[url] = entry
    with doc_cache_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    return results


def schedule_doc_cache_verification(
    interval_seconds: int, doc_cache_path: Path | None = None
) -> threading.Event:
    """Run ``verify_doc_cache`` periodically in a background thread.

    Returns a :class:`threading.Event` that can be set to stop the schedule.
    """

    stop_event = threading.Event()

    def loop() -> None:
        while not stop_event.is_set():
            verify_doc_cache(doc_cache_path)
            stop_event.wait(interval_seconds)

    threading.Thread(target=loop, daemon=True).start()
    return stop_event


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
        "violations.csv": [
            "session_id",
            "event_id",
            "platform",
            "sdk",
            "version_guess",
            "rule_id",
            "fail_code",
            "severity",
            "ts",
        ],
        "coverage.csv": [
            "session_id",
            "platform",
            "sdk",
            "version_guess",
            "label",
            "confidence",
            "source_lf_ids",
        ],
        "dictionary.csv": [
            "param",
            "aliases",
            "type",
            "unit",
            "min",
            "max",
            "mean",
            "stdev",
            "stability",
            "presence_map",
            "evidence_examples",
        ],
        "clusters.csv": [
            "cluster_id",
            "platform_guess",
            "sdk_guess",
            "signature",
            "representative_sessions",
            "n",
            "novelty_score",
        ],
        "sessions_index.csv": [
            "session_id",
            "platform",
            "sdk",
            "version_guess",
            "first_ts",
            "last_ts",
            "event_count",
            "file_source",
        ],
    }
    for name, head in other_files.items():
        with (out_dir / name).open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(head)

    populate_rules_index(out_dir)


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
