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

### Closing (TARS voice)

Honesty setting 90%: this isn't "magic," it's **determinism + weak supervision + small models + your taste** wired into a loop. Do the boring parts once (envelope, FSM, LFs), and the goblin handles the grinding: research, drafts, citations, tests, PRs. You approve; it learns; specs don't rot and v1 never breaks v3.
