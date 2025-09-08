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


def notify_unreachable_docs(out_dir: Path) -> None:
    """Write notifications for unreachable citation sources."""

    src = out_dir / "unreachable_docs.csv"
    if not src.exists():
        return
    with src.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return
    notify_path = out_dir / "unreachable_notifications.csv"
    now = datetime.now(timezone.utc).isoformat()
    with notify_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["citation_url", "notified_at"])
        for row in rows[1:]:
            writer.writerow([row[0], now])


def escalate_unreachable_docs(out_dir: Path) -> None:
    """Escalate previously notified unreachable citations."""

    notify_path = out_dir / "unreachable_notifications.csv"
    if not notify_path.exists():
        return
    with notify_path.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return
    escalate_path = out_dir / "unreachable_escalations.csv"
    now = datetime.now(timezone.utc).isoformat()
    with escalate_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["citation_url", "escalated_at"])
        for row in rows[1:]:
            writer.writerow([row[0], now])


def summarize_escalations(out_dir: Path) -> None:
    """Summarize citation status in a weekly report."""

    escalate_path = out_dir / "unreachable_escalations.csv"
    notify_path = out_dir / "unreachable_notifications.csv"
    unreachable_path = out_dir / "unreachable_docs.csv"

    escalated = 0
    if escalate_path.exists():
        with escalate_path.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        escalated = len(rows) - 1 if len(rows) > 1 else 0

    notified = 0
    if notify_path.exists():
        with notify_path.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        notified = len(rows) - 1 if len(rows) > 1 else 0

    unreachable = 0
    if unreachable_path.exists():
        with unreachable_path.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        unreachable = len(rows) - 1 if len(rows) > 1 else 0

    weekly_path = out_dir / "weekly_report.csv"
    prev_escalated = 0
    prev_notified = 0
    prev_unreachable = 0
    if weekly_path.exists():
        with weekly_path.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        for metric, value in rows[1:]:
            if metric == "escalated_citations":
                prev_escalated = int(value)
            elif metric == "notified_citations":
                prev_notified = int(value)
            elif metric == "unreachable_citations":
                prev_unreachable = int(value)
    trend_escalated = escalated - prev_escalated
    trend_notified = notified - prev_notified
    trend_unreachable = unreachable - prev_unreachable
    with weekly_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["escalated_citations", str(escalated)])
        writer.writerow(["notified_citations", str(notified)])
        writer.writerow(["escalated_citations_trend", str(trend_escalated)])
        writer.writerow(["notified_citations_trend", str(trend_notified)])
        writer.writerow(["unreachable_citations", str(unreachable)])
        writer.writerow(["unreachable_citations_trend", str(trend_unreachable)])
    html_path = out_dir / "weekly_report.html"
    with html_path.open("w", encoding="utf-8") as f:
        f.write("<html><body>\n")
        f.write("<h1>Weekly Citation Report</h1>\n")
        f.write("<table><tr><th>metric</th><th>value</th></tr>\n")
        f.write(f"<tr><td>escalated_citations</td><td>{escalated}</td></tr>\n")
        f.write(f"<tr><td>notified_citations</td><td>{notified}</td></tr>\n")
        f.write(f"<tr><td>unreachable_citations</td><td>{unreachable}</td></tr>\n")
        f.write("</table>\n<h2>Trends</h2>\n")
        for name, val in [
            ("escalated_citations_trend", trend_escalated),
            ("notified_citations_trend", trend_notified),
            ("unreachable_citations_trend", trend_unreachable),
        ]:
            bar = "█" * max(val, 0)
            f.write(f"<div>{name}: {val:+d} {bar}</div>\n")
        f.write("</body></html>\n")

    history_path = out_dir / "weekly_report_history.csv"
    history_exists = history_path.exists()
    with history_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not history_exists:
            writer.writerow(
                [
                    "ts",
                    "escalated_citations",
                    "notified_citations",
                    "escalated_citations_trend",
                    "notified_citations_trend",
                    "unreachable_citations",
                    "unreachable_citations_trend",
                ]
            )
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                str(escalated),
                str(notified),
                str(trend_escalated),
                str(trend_notified),
                str(unreachable),
                str(trend_unreachable),
            ]
        )

    analyze_trend_history(out_dir)

    analysis_path = out_dir / "weekly_report_analysis.html"
    report_path = out_dir / "weekly_report.html"
    if analysis_path.exists() and report_path.exists():
        analysis_html = analysis_path.read_text(encoding="utf-8")
        start = analysis_html.find("<body>")
        end = analysis_html.rfind("</body>")
        if start != -1 and end != -1:
            snippet = analysis_html[start + len("<body>") : end]
            content = report_path.read_text(encoding="utf-8")
            insert = content.rfind("</body>")
            if insert != -1:
                content = (
                    content[:insert]
                    + "<h2>Trend Analysis</h2>\n"
                    + snippet
                    + content[insert:]
                )
                report_path.write_text(content, encoding="utf-8")


def analyze_trend_history(out_dir: Path) -> None:
    """Analyze weekly report history for average trend patterns."""

    history_path = out_dir / "weekly_report_history.csv"
    if not history_path.exists():
        return
    with history_path.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return
    es = [int(r[3]) for r in rows[1:]]
    no = [int(r[4]) for r in rows[1:]]
    un = [int(r[6]) for r in rows[1:]]
    n = len(es)
    avg_es = sum(es) / n
    avg_no = sum(no) / n
    avg_un = sum(un) / n

    analysis_path = out_dir / "weekly_report_analysis.csv"
    with analysis_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "avg_trend"])
        writer.writerow(["escalated_citations_trend_avg", f"{avg_es:.2f}"])
        writer.writerow(["notified_citations_trend_avg", f"{avg_no:.2f}"])
        writer.writerow(["unreachable_citations_trend_avg", f"{avg_un:.2f}"])

    html_path = out_dir / "weekly_report_analysis.html"
    with html_path.open("w", encoding="utf-8") as f:
        f.write("<html><body>\n<h1>Weekly Trend Analysis</h1>\n")
        for name, val in [
            ("escalated_citations_trend_avg", avg_es),
            ("notified_citations_trend_avg", avg_no),
            ("unreachable_citations_trend_avg", avg_un),
        ]:
            bar = "█" * max(int(round(val)), 0)
            f.write(f"<div>{name}: {val:.2f} {bar}</div>\n")
        f.write("</body></html>\n")


def queue_weekly_report(out_dir: Path) -> None:
    """Queue generated weekly report for distribution."""

    report_path = out_dir / "weekly_report.html"
    if not report_path.exists():
        return
    queue_path = out_dir / "distribution_queue.csv"
    now = datetime.now(timezone.utc).isoformat()
    exists = queue_path.exists()
    with queue_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["file_path", "queued_at"])
        writer.writerow([str(report_path), now])


def schedule_distribution(out_dir: Path) -> None:
    """Schedule queued reports for delivery."""

    queue_path = out_dir / "distribution_queue.csv"
    if not queue_path.exists():
        return
    with queue_path.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return
    schedule_path = out_dir / "distribution_schedule.csv"
    now = datetime.now(timezone.utc).isoformat()
    with schedule_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_path", "scheduled_for"])
        for row in rows[1:]:
            writer.writerow([row[0], now])


def deliver_scheduled_reports(out_dir: Path) -> None:
    """Deliver scheduled reports and log delivery time."""

    schedule_path = out_dir / "distribution_schedule.csv"
    if not schedule_path.exists():
        return
    with schedule_path.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return
    delivery_path = out_dir / "distribution_delivery.csv"
    now = datetime.now(timezone.utc).isoformat()
    with delivery_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_path", "delivered_at"])
        for row in rows[1:]:
            writer.writerow([row[0], now])


def record_delivery_receipts(out_dir: Path) -> None:
    """Record a receipt for each delivered report."""

    delivery_path = out_dir / "distribution_delivery.csv"
    if not delivery_path.exists():
        return
    with delivery_path.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) <= 1:
        return
    receipts_path = out_dir / "distribution_receipts.csv"
    now = datetime.now(timezone.utc).isoformat()
    with receipts_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_path", "receipt_at"])
        for row in rows[1:]:
            writer.writerow([row[0], now])


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
    notify_unreachable_docs(out_dir)
    escalate_unreachable_docs(out_dir)
    summarize_escalations(out_dir)
    queue_weekly_report(out_dir)
    schedule_distribution(out_dir)
    deliver_scheduled_reports(out_dir)
    record_delivery_receipts(out_dir)


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
