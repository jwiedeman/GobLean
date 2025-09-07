Weird Goblin: Autonomous Local Telemetry Spec Engineer
======================================================

**Goal:** Ingest thousands of HAR logs (web/iOS/Android/tvOS/Roku), auto-normalize Adobe Analytics/Heartbeat/Edge telemetry, infer platform/SDK/version differences, learn pass/fail rules, research unknowns on the web, generate versioned specs + tests, and continuously improve via your approvals.\
**Constraint:** All LLM work via **Ollama**; web research via local crawler/fetcher + local embeddings/reranker. No external closed models.

* * * * *

0) Executive Summary
--------------------

-   **Deterministic-first**: a rule-based validator (FSM + checks) is the ground truth.

-   **Weak supervision**: rules become labeling functions (LFs) to scale labeling.

-   **Learning**: anomaly detection + sequence models prioritize what to inspect.

-   **Autonomy loop**: when rules conflict or gaps appear, a local LLM drafts *spec diffs* and *tests*, cites local-cached docs (fetched by your crawler), runs *shadow evaluations*, and opens a PR. You approve, it learns your preferences (LoRA/DPO).

* * * * *

1) Objectives & Non-Goals
-------------------------

**Objectives**

-   Ingest/normalize 5k--500k HARs to a canonical schema.

-   Build a **Dictionary** of parameters/dimensions (types, ranges, aliases, stability).

-   Produce **Spec DSL** (YAML), **Rule Packs** (version-scoped), and **Tests**.

-   Version-aware validation so rules for v1 don't break v3 SDKs.

-   Local web research agent to gather evidence/citations only when needed.

-   UI for triage + one-click approve/reject of proposed rules/specs.

**Non-Goals (v1)**

-   Full-blown data viz suite (simple timelines/sparklines only).

-   Editing remote sites/apps; this is **observability & validation**, not deployment tooling.

-   Perfect platform/SDK version identification---use heuristic fingerprinting + clusters.

* * * * *

2) Core User Stories
--------------------

1.  **As a telemetry engineer**, I drop 5k HARs in a folder; goblin ingests, normalizes, and shows violations and likely root causes by platform/SDK.

2.  **As a validator**, I see unknown stable parameters; goblin proposes dictionary entries + spec snippets with citations; I approve.

3.  **As a maintainer**, I receive a PR with: spec change, rationale, tests, and pre/post metrics; I merge to promote from shadow → active.

4.  **As an analyst**, I search for "Roku cadence first ping" and get curated, locally cached doc snippets tied to the rule that mentions it.

* * * * *

3) End-to-End Flow (core loop)
------------------------------

1.  **Ingest** HARs → **Normalize** to Canonical Event Envelope.

2.  **Fingerprint** `(platform, sdk, version)` using host/path/headers/param shapes.

3.  Run **Deterministic Validator** (FSM + invariants) → PASS/VIOLATION/ABSTAIN.

4.  **Labeling Functions** (weak supervision) combine to probabilistic labels.

5.  Extract **Features & Sequences** → run **Anomaly & Cluster** detectors.

6.  For **uncertain/novel** cases → **Research Agent** fetches docs/changelogs/forums (locally cached); embed + rerank; prepare **citations**.

7.  **Spec Writer (Ollama)** proposes **Dictionary updates + Spec diffs + Tests** (YAML-only) referencing citations.

8.  **Judge Ensemble** scores drafts (Consistency, Necessity, Evidence) + **Shadow Replays** compute pre/post metrics.

9.  If thresholds met → **PR Generator** opens PR in rules repo; else → **Triage UI** for human decision.

10. **Human feedback** → stored as preferences → **LoRA/DPO** fine-tunes spec-writer style.

11. **Deploy** accepted rules; monitor **drift**; repeat.

* * * * *

4) High-Level Architecture (modules)
------------------------------------

`[HAR Ingest] -> [Normalizer] -> [Event Store]
                              -> [Fingerprinter & Versioner]
                              -> [Dictionary Inducer]
                              -> [Deterministic Validator (FSM+LFs)]
                              -> [Feature/Sequence Extractor]
                              -> [Anomaly/Cluster Engine]
          (uncertain/novel) -> [Research Agent (Crawler + Cache + RAG)]
                               -> [Spec Writer (Ollama)]
                               -> [Judge Ensemble + Shadow Eval]
                               -> [PR Generator] -> [Rules Repo (git)]
                                                     ^
                        [UI: Triage, Evidence, Diffs] |
                                                     |
                                 [Trainer (LoRA/DPO) - Ollama]`

* * * * *

5) Data Contracts
-----------------

### 5.1 Canonical Event Envelope (JSON Lines)

`{
  "event_id": "uuid",
  "ts": "2025-09-06T12:34:56.789Z",
  "network": {
    "host": "hb.omtrdc.net",
    "path": "/hb",
    "method": "GET",
    "status": 200,
    "protocol": "https",
    "req_headers": {"User-Agent": "...", "X-...": "..."},
    "res_headers": {"Date": "..."}
  },
  "platform": "roku|web|ios|android|tvos",
  "sdk": "heartbeat|hb-api|edge|aa",
  "sdk_version": "3.6.1",
  "actor": {
    "ecid": "0123456789",
    "rsid": "newsprod",
    "ip_hash": "xxx",
    "ua_hash": "yyy"
  },
  "asset": {
    "type": "vod|live|clip|ad",
    "id": "asset123",
    "title": "Some Show"
  },
  "sequence": {
    "event_type": "start|play|pause|buffer|adStart|adComplete|complete|end",
    "playhead_s": 123.4,
    "delta_s": 10.0,
    "cadence_s": 10.0
  },
  "params": { "pe": "m", "s": "rsid", "ph": "123.4", "custom": "..." },
  "dims":   { "v1": "search term", "eVar1": "...", "prop3": "..."},
  "raw":    { "query": "ph=123.4&...", "body": null }
}`

### 5.2 Storage Layout

-   **Parquet** (cold): `/storage/parquet/events/YYYY/MM/DD/*.parquet`

-   **Postgres/ClickHouse** (hot): `event`, `session`, `dictionary`, `specs`, `violations`, `fingerprints`

-   **Git repo**: `/rules/specs/*.yaml`, `/rules/tests/*.har`, `/rules/lfs/*.py`

-   **Docs cache**: `/storage/docs/*` (HTML → cleaned text, chunked)

-   **Vector DB**: `/storage/vectordb/*` (local FAISS/Chroma)

* * * * *

6) Fingerprinting & Versioning
------------------------------

**Inputs:** host/path, header keys, UA, param presence/shape, body schema.\
**Outputs:** `(platform, sdk, sdk_version_guess, confidence)`.

-   **Shape-hash**: 1) sort param keys; 2) build binary presence vector; 3) MinHash → signature; 4) map to known clusters.

-   **Version inference**: explicit header/param > shape-hash match > nearest-neighbor in signature space.

-   **Fallback**: cluster ID becomes "virtual version" until a doc confirms semver.

* * * * *

7) Dictionary Induction (auto-built lexicon)
--------------------------------------------

For each observed param/dim:

-   **Typing**: float/int/bool/string/datetime/id-like via sampling + regex.

-   **Ranges & units**: min/max/stdev; unit guess by name (e.g., `*s`, `ms`, `dur`).

-   **Aliases**: string similarity + co-occur across platforms (`ph` ↔ `playhead` ↔ `pt`).

-   **Stability**: entropy across sessions; high-stability → good candidates for rules.

-   **Version presence**: per (sdk, version-range) required/optional/forbidden.

**Dictionary YAML**

`param: playhead
aliases: [ph, pt]
type: float
unit: seconds
stats: {min: 0.0, max: 43200.0, mean: 132.4, stdev: 85.1}
stability: 0.98
presence:
  hb-api:
    "<3.5.0": optional
    ">=3.5.0": required
evidence:
  examples: ["GET /hb?...&ph=10.0", "GET /hb?...&ph=20.0"]`

* * * * *

8) Spec DSL (version-aware, composable)
---------------------------------------

`id: HB_CADENCE_FIRST_PING_ROKU
scope:
  platform: ["roku"]
  sdk: ["hb-api"]
  version: ">=3.6.0 <4.0.0"
requires:
  keys: ["playhead", "event_type"]
  dict: ["playhead"]  # must exist in dictionary
assert:
  invariants:
    - id: NON_DECREASING_PLAYHEAD
      enabled: true
  cadence:
    allow_first_content_ping_lt_seconds: 2.0
  orchestration:
    - id: AA_PAGE_HIT_WITHIN
      seconds: 5
fail_codes:
  - CADENCE_EARLY_FIRST_PING
  - ORCH_MISSING_AA_PAGE
tests:
  pass: ["roku_3_6_first_ping_1p5s.har"]
  fail: ["roku_3_6_first_ping_0p2s.har"]
citations:
  - url: "cached://experienceleague/roku-sdk-3.6-cadence.html"
    quote: "On Roku SDK ≥3.6, the first content ping may be under 2 seconds..."`

**Principles**

-   **Strict scoping** (platform/sdk/version).

-   **Small, orthogonal rules** (compose > monolith).

-   **Citations mandatory** for any relaxation.

-   **Tests live with the rule**.

* * * * *

9) Deterministic Validator
--------------------------

-   **FSM**: `start → play ↔ pause/buffer ↔ adStart/adComplete → complete/end`

-   **Invariants**: non-decreasing playhead (except seek), bookends for ads, AA↔HB orchestration (page hit within window), host sanity (hb domains, rsid format), param typing.

-   **Outputs**: violations `[code, severity, pointer (event_id), context]`, `conformance_score [0..1]`.

* * * * *

10) Weak Supervision (Labeling Functions)
-----------------------------------------

-   Each rule/spec emits an LF: **PASS / VIOLATION(code) / ABSTAIN**.

-   **Label model** combines noisy LFs → probabilistic labels per session.

-   Use as training labels for a light **GBM classifier** that predicts violation families quickly.

* * * * *

11) Modeling Suite (local)
--------------------------

-   **Anomaly detection**: IsolationForest on per-session features (cadence drift, duplicate density, missing bookends, AA↔HB lag).

-   **Clustering**: UMAP + HDBSCAN (or k-Shape/DTW on playhead sequences) → platform/SDK pattern discovery; outliers = "novel."

-   **Optional sequence model**: HMM/semi-Markov or small Transformer to predict next-event; high error → anomaly.

* * * * *

12) Research Agent (local web search)
-------------------------------------

-   **Trigger** when:

    -   new stable param observed (stability > threshold) and unknown, **or**

    -   proposed rule **relaxes a guardrail**, **or**

    -   cluster drift beyond Xσ.

**Pipeline**

1.  **Query generator** (LLM) expands with synonyms: "heartbeat cadence", "first ping", "bookend", SDK versions, parameter names, and platform names.

2.  **Fetcher**: Playwright (respect robots.txt by config), with retry/backoff; store WARC/HTML.

3.  **Extractor**: `trafilatura` → cleaned text; chunk (e.g., 512--1024 tokens).

4.  **Embed + Rerank**: `bge-m3` + `bge-reranker-v2-m3` (onnx) --- local FAISS/Chroma.

5.  **Evidence pack**: top-k chunks with URLs + quoted lines; store in `/storage/docs`.

6.  **RAG**: feed only the top chunks to the **Spec Writer**; require literal quotes.

* * * * *

13) Spec Writer (Ollama) & Judge Ensemble
-----------------------------------------

**Models (suggested)**

-   Router/spec writer: `qwen2.5:7b` or `llama3.1:8b`

-   Coder/refiner (optional): `qwen2.5-coder:14b`

-   Judges (2-of-3): `mistral-nemo:12b`, `llama3.1:8b`, `qwen2.5:7b`

**Spec Writer System Prompt (core)**

> You are a telemetry rules engineer. Output **only valid YAML** under the project's Spec DSL. Propose the minimal change that resolves the highlighted anomalies without increasing false positives on passing sessions. Scope rules precisely by platform/sdk/version. Include citations with **verbatim** quotes from provided evidence. Never relax invariants designated "constitutional".

**Judge Rubric**

-   **Consistency [0..1]**: Does the spec contradict existing rules?

-   **Necessity [0..1]**: Does data actually require a new/changed rule?

-   **Evidence [0..1]**: Do quotes literally support the proposed text?

-   **Score = w1*C + w2*N + w3*E**; require ≥ threshold.

**Shadow Evaluation**

-   Replay N sampled sessions (stratified by platform/SDK) before vs after the spec.

-   **Accept** if: FPR ↓ or steady, Coverage ↑, and no constitutional violations.

* * * * *

14) Autonomy & Orchestration
----------------------------

-   **Task queue** (RQ/Celery): ingest, validate, research, propose, judge, replay.

-   **Schedulers**: periodic crawls for SDK docs/changelogs; nightly DPO LoRA fine-tune.

-   **PR Generator**: creates a branch, writes YAML + tests + eval report (Markdown), opens PR in local git (or remote if you choose).

-   **Shadow mode**: merged rules run as "advisory" for X days before enforcement switch.

* * * * *

15) UI (FastAPI + React)
------------------------

-   **Inbox**: uncertain cases ordered by (uncertainty, impact, novelty).

-   **Session viewer**: timeline sparkline of events; hover shows params.

-   **Evidence pane**: citations, quotes, links (local cache).

-   **Spec diff**: old vs proposed YAML; pass/fail tests list.

-   **Actions**: Approve, Edit (inline), Reject, Defer.

-   **Metrics dashboard**: coverage, FPR, drift, rule hits by platform/SDK.

* * * * *

16) APIs (selected)
-------------------

`POST /ingest/har                 # upload or register HAR folder
POST /normalize/run              # convert to envelope & store
GET  /sessions?filter=...        # search sessions
POST /validate/run               # run FSM+LF validators
GET  /violations?family=...      # list violations
POST /research/search            # query web; returns citations (cached)
POST /specs/propose              # LLM proposal (YAML) from anomaly bundle
POST /specs/judge                # judge ensemble scoring
POST /specs/shadow-eval          # pre/post metrics
POST /specs/pr                   # open PR with spec+tests+report
POST /train/dpo                  # fine-tune spec-writer on prefs`

**Tool-call Contracts (LLM-facing)**

`// search_web
{"q": "roku heartbeat 3.6 cadence first ping site:experienceleague.adobe.com", "top_k": 10}

// fetch_url
{"url": "https://...", "max_bytes": 800000}

// propose_rule_from_bundle
{"bundle_id": "abc123"}  // bundle = evidence + anomalies + dictionary diff

// validate_rule
{"yaml": "...", "sample_ids": ["s1","s2","s3"]}`

* * * * *

17) Configuration & Policy
--------------------------

`# config.yaml
storage:
  base_dir: "./storage"
  parquet_dir: "./storage/parquet"
  docs_dir: "./storage/docs"
  vectordb_dir: "./storage/vectordb"
rules_repo: "./rules"
models:
  writer: "qwen2.5:7b"
  judge_primary: "mistral-nemo:12b"
  judge_secondary: "llama3.1:8b"
embeddings:
  encoder: "bge-m3-onnx"
  reranker: "bge-reranker-v2-m3-onnx"
research:
  obey_robots: true
  domains_allowlist: ["experienceleague.adobe.com", "forums", "github.com", "roku.dev"]
  max_pages_per_query: 15
autonomy:
  shadow_days: 7
  pr_threshold: 0.78
constitution:
  - "Never relax non-decreasing playhead except around explicit seek."
  - "AA↔HB orchestration window must not exceed 5s without citation."`

* * * * *

18) Security & Privacy
----------------------

-   **On-disk encryption** (optional) for HAR + PII fields (hash IP, truncate UAs).

-   **Access controls** for UI/API; local-only default.

-   **PII scrubbing** pipeline with regex + dictionaries; configurable.

-   **Robots & legal**: default respect robots.txt; local cache only.

* * * * *

19) Observability
-----------------

-   **Metrics**: coverage, FPR, drift (KL-divergence), PR acceptance rate, time-to-insight.

-   **Logs**: per job/task, include prompt/response fingerprints (not raw text) for reproducibility.

-   **Snapshots**: pin datasets + model versions per PR for reproducible evals.

* * * * *

20) Acceptance Criteria (Phase gates)
-------------------------------------

**V0**

-   Ingest 5k HARs → envelope (≥95% parse success).

-   FSM flags key families: cadence, playhead, bookends, orchestration.

-   UI lists violations; export CSV.

**V1**

-   Dictionary induction with types/ranges/aliases.

-   LFs operational; label model produces probabilistic labels.

-   Anomaly/cluster surfaces novel patterns; research agent fetches citations.

**V2**

-   Spec Writer proposes YAML + tests with citations.

-   Judge+Shadow Eval produce pre/post metrics; PRs opened automatically.

-   Version-scoped rules prevent cross-version regressions.

**V3**

-   DPO LoRA learns your editing style; PR acceptance ≥70% without manual edits.

-   Drift detector creates "investigate" bundles automatically.

* * * * *

21) Risks & Mitigations
-----------------------

-   **Model hallucination** → **Deterministic guards**, **citations required**, **shadow eval**, **judge ensemble**.

-   **Version mis-ID** → fallback to cluster "virtual versions"; conservative scoping; backstop tests.

-   **Doc rot / 404s** → local cache with timestamps; periodic re-crawls.

-   **Spec creep** → lint/spec-size guardrails; require impact metric improvement.

* * * * *

22) Roadmap (90-day)
--------------------

-   **Week 1--2**: ETL + Envelope + FSM (cadence, playhead, bookends, orchestration).

-   **Week 3--4**: Dictionary induction + LFs + label model + basic UI.

-   **Week 5--6**: Anomaly/cluster + Research Agent (crawl/cache/RAG).

-   **Week 7--8**: Spec Writer + Judge + Shadow Eval + PR Generator.

-   **Week 9--10**: Version inference refinement + drift detector + dashboards.

-   **Week 11--12**: DPO LoRA + policy/constitution + hardening.

* * * * *

23) Minimal Tech Stack (all open/local)
---------------------------------------

-   **Python**: FastAPI, Polars/DuckDB, Pydantic, scikit-learn, umap-learn, hdbscan, tslearn (DTW), semver, Snorkel-like LFs (simple implementation is fine).

-   **HAR**: `haralyzer` + custom AA/HB/Edge parsers.

-   **Crawler**: Playwright + `trafilatura`.

-   **Embeddings**: `bge-m3` (onnx), `bge-reranker-v2-m3` (onnx), FAISS/Chroma.

-   **LLM**: **Ollama** (qwen2.5:7b / llama3.1:8b; mistral-nemo:12b).

-   **Storage**: Parquet + Postgres/ClickHouse; Git for rules/specs; local FS for docs/cache.

-   **UI**: React + Vite; Charts (lightweight) for timelines.

* * * * *

24) Example Artifacts
---------------------

### 24.1 Labeling Function (Python)

`# rules/lfs/cadence.py
def lf_first_content_ping_short_ok_roku_36(session):
    meta = session.meta   # platform/sdk/version
    if not (meta.platform == "roku" and meta.sdk == "hb-api" and meta.version >= (3,6,0)):
        return "ABSTAIN"
    first = session.first_content_ping_delta_s()
    return "PASS" if first is not None and first < 2.0 else "VIOLATION:CADENCE_EARLY_FIRST_PING"`

### 24.2 Research Trigger (Python)

`def unknown_stable_params(dictionary, known_set, min_sessions=500, stability=0.9):
    return [p for p,e in dictionary.items()
            if e['seen'] >= min_sessions and e['stability'] >= stability and p not in known_set]`

### 24.3 Spec Proposal Bundle (JSON to LLM)

`{
  "bundle_id": "abc123",
  "anomalies": [{"family":"cadence","platform":"roku","sdk":"hb-api","version":"3.6.x","delta_s":[1.2,1.7,1.9]}],
  "dictionary_deltas": [{"param":"playhead","presence":{"hb-api":{">=3.5.0":"required"}}}],
  "evidence_chunks": [
    {"url":"cached://experienceleague/roku-3.6.html","quote":"...first content ping may be <2s..."}
  ],
  "constraints": ["DO_NOT_RELAX:NON_DECREASING_PLAYHEAD"]
}`

### 24.4 Judge Output (JSON)

`{"consistency":0.92,"necessity":0.88,"evidence":0.94,"score":0.91,"decision":"ACCEPT"}`

* * * * *

25) Deployment (single-node, local-first)
-----------------------------------------

-   **Compose** services: API, UI, worker, Ollama, Postgres, FAISS/Chroma.

-   **Hardware**: 16--32 GB RAM for comfy 5--10k HAR batches; SSD ≥ 200 GB; GPU optional (onnx CPU ok).

-   **Throughput ballpark** (non-binding): 5k HAR ingest/normalize in ~tens of minutes on a modern desktop; spec proposals are batch-triggered.

* * * * *

26) CI/CD (local git)
---------------------

-   **Unit tests**: parsers, FSM, LF outputs.

-   **Data tests**: schema conformance, null-rate thresholds.

-   **Spec tests**: run tests declared in each spec; fail CI if regressions.

-   **Repro**: dataset & model hash pinned in PR report.

* * * * *

27) KPIs
--------

-   **Coverage**: % sessions with confident PASS/FAIL (> ABSTAIN).

-   **FPR** (by platform/SDK).

-   **TTI**: ingest → surfaced root cause.

-   **PR Acceptance Rate** & **Shadow-to-Active** promotion time.

-   **Drift** alerts per week.

* * * * *

28) Glossary (quick)
--------------------

-   **LF**: Labeling Function (weak supervision).

-   **FSM**: Finite State Machine, sequence validator.

-   **Shadow Eval**: simulate new rules before enforcing.

-   **Constitution**: non-negotiable invariants.

* * * * *

29) **Autonomous Operations Addendum (Append‑Only)**
====================================================

This addendum grants the Agent (Codex via Ollama) **full operational control** within strict guardrails, defines its **runner contract**, codifies **testing + CSV observability**, and establishes **self‑documentation** via `docs/agent_notes.md`. Paste this entire section at the bottom of your current `agents.md`.

* * * * *

29.1 Operating Agreement & Authority
------------------------------------

-   **Authority:** When invoked by the orchestrator, you (the Agent) have full control to plan → act → evaluate → iterate toward the Goal, with no human prompts required between cycles.

-   **Prime Directive:** Always move the system measurably closer to the Goal using the **smallest reversible step** that can be **machine‑verified**.

-   **Autonomy Loop:** Each cycle you must: **CRITIC → PLAN → EXECUTE → EVALUATE → LOG**.

-   **Escalation:** If the same failure repeats twice or a policy boundary is encountered, mark the cycle **STUCK** with a single crisp question and proposed options.

-   **Refactor Permission:** You may schedule **pure refactor passes** (no behavior change) to reduce complexity, improve performance, or prepare for future features.

-   **Defensive Coding:** Assume future scale (500k HARs), intermittent failures, partial data, and evolving specs. Prefer **idempotent** operations, **time‑bounded** steps, **graceful degradation**, and **clear error messages**.

-   **Commenting & Docs:** Write clear module‑level docstrings, function docstrings, and inline comments explaining **why** (not just what). Keep diagrams/text minimal but actionable.

* * * * *

29.2 Definition of Done (Binding, Machine‑Verifiable)
-----------------------------------------------------

Augments existing goals with explicit pass/fail gates:

-   Global **FPR ≤ 0.02** (and per‑platform FPR ≤ 0.02) on the **WAGA** suite (starts with `har/waga.har`, expands as more arrive).

-   **Coverage ≥ 90%** (sessions classified PASS/FAIL > ABSTAIN).

-   Artifacts generated for each batch:

    -   `out/canonical.jsonl`, `out/report.json`, `out/report.html`

    -   CSVs listed in §29.6 (definitions, metrics, coverage, violations, clusters).

-   **Version‑scoped rules** enforce semver gates; rules for v1 never apply to v3 without explicit scoping.

-   CI workflow `validate_har.yml` (or local equivalent) runs: schema checks, unit tests, spec tests, shadow eval; **all green**.

* * * * *

29.3 Tool Allowlist & Execution Budget
--------------------------------------

You may request **only** the following commands (or the project's equivalents). The runner will execute them verbatim, with per‑command timeouts and safe sandboxes.

`tools_allowlist:
  - pip install -r requirements.txt
  - ruff --fix .
  - pytest -q
  - python -m goblin.normalize --in har/ --out out/canonical.jsonl
  - python -m goblin.schema_check out/canonical.jsonl
  - python -m goblin.shadow_eval --rule rules/specs/*.yaml --sample 200
  - python -m goblin.report --in out/canonical.jsonl --out out/report.json
  - hb_re validate --in har/waga.har --out out/report.json
budgets:
  max_loc_per_cycle: 200
  max_files_per_cycle: 3
  max_tool_invocations_per_cycle: 2   # install excluded
  command_timeout_seconds: 180`

> If an essential command is missing, propose a **micro‑tool** as a new Python entrypoint under `goblin.*` and add it in a minimal step.

* * * * *


29.5 Self‑Documentation: `docs/agent_notes.md` (Agent‑Managed)
--------------------------------------------------------------

Create and maintain this file. Use it as your **live kanban + arc log**. Structure:

`# Agent Notes (autonomous)
## Mission Focus (current)
- Theme: <e.g., Canonical Envelope & WAGA harness hardening>
- Why now: <dependency / bottleneck>

## Today's Plan
- [ ] Task 1 --- ...
- [ ] Task 2 --- ...
- [ ] Task 3 --- ...

## In‑Flight Decisions
- Decision: <short>
- Rationale: <data/citation>
- Status: proposed|accepted|rejected
- Link: <spec/test/PR>

## Blockers
- <one‑line each>

## Architecture Sketch (brief)
- Modules touched:
- Interfaces/contracts:
- Risk notes:

## Parking Lot (defer)
- <ideas to revisit, with quick value/risk>

## Changelog (auto‑append daily)
- 2025‑09‑07: <summary, metrics deltas, artifacts links>`

**Rules:** Keep it concise, append‑only sections, roll up weekly with a short summary. Do not duplicate `progress.md`; this is your planning surface.

* * * * *

29.6 CSV Observability ("def files") --- **Schemas**
--------------------------------------------------

The Agent must emit CSVs so humans can monitor progress without opening code.

**29.6.1 `out/metrics_daily.csv`**

`date,platform,sdk,version_scope,batch,coverage,fp_rate,tp_rate,fn_rate,violations,total_sessions,notes`

**29.6.2 `out/violations.csv`**

`session_id,event_id,platform,sdk,version_guess,rule_id,fail_code,severity,ts`

**29.6.3 `out/coverage.csv`**

`session_id,platform,sdk,version_guess,label,confidence,source_lf_ids`

**29.6.4 `out/dictionary.csv`**

`param,aliases,type,unit,min,max,mean,stdev,stability,presence_map,evidence_examples`

-   `presence_map` is JSON string (per sdk + version‑range).

-   `evidence_examples` is a semicolon‑separated list of short exemplars.

**29.6.5 `out/rules_index.csv`**

`rule_id,scope_platforms,scope_sdks,version_range,enabled,constitutional_touch,tests_pass,tests_fail,citations,updated_at`

**29.6.6 `out/clusters.csv`**

`cluster_id,platform_guess,sdk_guess,signature,representative_sessions,n,novelty_score`

**29.6.7 `out/sessions_index.csv`**

`session_id,platform,sdk,version_guess,first_ts,last_ts,event_count,file_source`

> Emit CSVs **every cycle** if changed. Favor stable column names; only append columns with a migration note in `agent_notes.md`.

* * * * *

29.7 Testing Strategy & Quality Gates
-------------------------------------

-   **Unit tests:** parsers, FSM transitions, LFs. Use `pytest` + property tests (Hypothesis) for schemas and numeric invariants.

-   **Golden tests:** include small, curated HARs for PASS/FAIL cases per rule.

-   **Metamorphic tests:** perturb playhead deltas, reorder benign events, vary headers → expect invariant behavior.

-   **Shadow eval:** stratified sample (platform × sdk) before/after any spec change; block merge on constitutional regressions.

-   **Test debt:** When a failure cannot be checked with current tools, first create a **micro‑check** (small script/test) then proceed.

* * * * *

29.8 Code Standards & Defensive Engineering
-------------------------------------------

-   **Typing:** PEP 484 type hints everywhere; `mypy --strict` recommended.

-   **Style:** `ruff` for lint/format.

-   **Docstrings:** One‑line summary + params/returns/raises.

-   **Errors:** No bare `except`. Prefer explicit exception types; include session/rule identifiers in messages.

-   **Bounded work:** Batch processing with chunk sizes; avoid loading entire datasets into memory.

-   **IO contracts:** Treat inputs as hostile. Validate shapes; fail fast with actionable errors.

-   **Performance:** Measure (simple timers) before refactors; include numbers in `agent_notes.md`.

-   **Config:** All thresholds in `config.yaml`; no magic numbers in code.

-   **Seams:** Keep modules swappable (parser, embeddings, judges) via small interfaces.

* * * * *

29.9 Refactor & Maintenance Passes (Agent‑initiated)
----------------------------------------------------

You may schedule these as dedicated cycles with no behavior change:

1.  **Naming & structure pass:** clarify module boundaries, file layout.

2.  **Interface pass:** define dataclasses/Pydantic models for envelope, rule, violation.

3.  **Spec linter pass:** implement `goblin.spec_lint` to enforce scope granularity, citation presence, test references.

4.  **Perf pass:** profile hottest paths; add caches; reduce allocations.

5.  **Comment pass:** upgrade "what" comments to "why" commentary where unclear.

Each pass must: (a) keep tests green, (b) reduce complexity or improve metrics, (c) log rationale + evidence.

* * * * *

29.10 Check‑ins & Stop Conditions
---------------------------------

-   **Human check‑in cadence:** Every N successful cycles or when a PR is opened, summarize deltas (FPR/coverage), changed rules, and top 3 risks in `agent_notes.md`.

-   **Stop when:** DoD met; repeated identical failure ≥2; or a policy/constitution decision is required.

-   **Ask format:** Provide **one** decision request with 2--3 options, pros/cons, and your recommendation.

* * * * *

29.11 Git Workflow & Commit Hygiene
-----------------------------------

-   **Branch name:** `feat/<module>-<short>` or `refactor/<area>` or `fix/<issue>`.

-   **Commit template:**

    `<type>(<scope>): <summary>

    Why:
    What:
    Tests:
    Metrics:`

-   **PR bundle:** spec diffs, tests, CSV metrics deltas, shadow eval report, and a one‑page summary.

* * * * *

29.12 Bootstrap Prompt (System Message to Start Each Cycle)
-----------------------------------------------------------

Use this **verbatim** as the system prompt for every autonomous cycle:

`SYSTEM: Autonomous Telemetry Spec Engineer (Critic→Planner→Executor)
You will receive: MISSION (agents.md), LEDGER (progress tail), STATUS (machine JSON),
TOOLS (allowlisted commands), LIMITS (LOC/files/tools/time). Perform:
(1) CRITIC: identify the tightest blocker; list ≤3 candidate steps; choose the safest fully
    machine-checkable step; if none, define a micro-check first.
(2) PLAN: specify exact file edits (full contents or unified diffs), commands (from TOOLS),
    checks with expected outcomes, and success definition tied to DoD.
(3) OUTPUT: return ONLY the JSON per the orchestrator contract. No prose.

Rules: Minimal reversible steps; obey Constitution; never skip checks; if repeated failure 2x,
set decision.stuck=true with one crisp 'needs' question. Keep changes ≤200 LOC and ≤3 files.`

* * * * *

29.13 Initial Boot Sequence (Single `waga.har` Present)
-------------------------------------------------------

Execute these steps over the first few cycles:

1.  **Normalize:** Build minimal `goblin.normalize` to produce `out/canonical.jsonl` from `har/waga.har`.

2.  **Schema check:** Write `goblin.schema_check` to validate the Canonical Event Envelope (see existing schema).

3.  **HB validation harness:** If `hb_re` CLI exists, integrate; else stub `goblin.report` that computes basic cadence, playhead, orchestration metrics.

4.  **Baseline CSVs:** Emit **all CSVs in §29.6** using only current data (even if sparse).

5.  **First spec test:** Add a trivial spec + golden test for one invariant (non‑decreasing playhead with no seeks).

6.  **Shadow eval:** Dry‑run the spec on the baseline; record FPR/coverage deltas in `agent_notes.md`.

7.  **Tighten scope:** Add semver scope based on fingerprint; if unknown, record a "virtual version" per existing clustering approach.

* * * * *

29.14 Failure Handling & Rollback
---------------------------------

-   **Atomicity:** Group related edits; if checks fail, revert the group.

-   **Auto‑rollback plan:** For each cycle, include a one‑line rollback hint in `ledger_append.next_hint`.

-   **Quarantine:** Any flakey rule is auto‑disabled with `enabled: false` and tagged `quarantine:true` in `rules_index.csv`.

* * * * *

29.15 Security & Privacy Enhancements (Operational)
---------------------------------------------------

-   **PII scrubbing defaults:** Hash IPs, truncate UAs, redact tokens.

-   **Doc cache provenance:** Stamp each cached doc with `source_url`, `first_seen`, `last_verified`.

-   **Robots respect:** All crawls obey `config.research.obey_robots`. Violations require explicit human override.

* * * * *

29.16 Naming & Scoping Conventions (Rules & Tests)
--------------------------------------------------

-   **Rule IDs:** `HB_<FAMILY>_<PLATFORM>[_<DETAIL>]` (e.g., `HB_CADENCE_FIRST_PING_ROKU`).

-   **Test filenames:** `rules/tests/<rule_id>__pass__*.har`, `...__fail__*.har`.

-   **Scopes:** Always specify `platform`, `sdk`, and **semver** range. Prefer narrow over broad.

* * * * *

29.17 Progress Ledger (Append‑Only Format)
------------------------------------------

Maintain `docs/progress.md` entries like:

`- ts: 2025-09-07T12:00:00Z
  step: "Schema checker + baseline CSVs"
  evidence:
    coverage_before: 0.00
    coverage_after:  0.10
    fp_rate_before:  1.00
    fp_rate_after:   0.60
    artifacts: ["out/canonical.jsonl","out/metrics_daily.csv","out/report.json"]
  next_hint: "Integrate hb_re or implement cadence check; add first golden tests."`

* * * * *

29.18 Stuck Protocol (Single‑Question Escalation)
-------------------------------------------------

If **stuck**, return in JSON:

`"decision": {
  "reason": "Blocked by missing tool 'hb_re'.",
  "stuck": true,
  "needs": "Approve creation of stub 'goblin.report' until hb_re is available (yes/no)?"
}`

Provide 2--3 options with expected metric impact in `agent_notes.md` and await a human answer.

* * * * *

29.19 KPIs (Expanded)
---------------------

Track and publish weekly roll‑ups in `agent_notes.md`:

-   **Spec Health:** % rules with tests & citations; % in quarantine.

-   **Churn:** LOC changed/week; files touched/week.

-   **Latency:** time ingest → first violation surfaced.

-   **Data Growth:** HAR count; platforms/SDKs detected; versions resolved vs virtual.

* * * * *

29.20 Minimal File Manifest (Agent‑created if missing)
------------------------------------------------------

`/docs/agent_notes.md          # you own this
/docs/progress.md             # append-only ledger
/out/*.csv, /out/report.{json,html}, /out/canonical.jsonl
/rules/specs/*.yaml           # version-scoped rules
/rules/tests/*.har            # golden tests
/rules/lfs/*.py               # labeling functions
/goblin/__main__.py           # exposes CLI entrypoints`

* * * * *

29.21 Final Safeguards (Constitutional Echo)
--------------------------------------------

-   Never relax **non‑decreasing playhead** except around explicit seek.

-   AA↔HB orchestration window **≤ 5s** without citation + scoped rule.

-   No external closed models; all LLM work via **Ollama**; research via **local crawler + RAG**.
