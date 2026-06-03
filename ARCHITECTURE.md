# Architecture

This document describes the technical design of GitSight: its modules, data flow, API contract, and design decisions.

---

## High-Level Overview

```
Browser
  └── GET /          → index.html (React SPA)
  └── POST /api/analyze → FastAPI → analyzer ─┬→ attribution (ownership + effort)
                                              ├→ quality (function-granularity)
                                              └→ integrity (forensic flags)
                                                 → scoring → JSON response
```

GitSight is a stateless, single-process web application positioned as a **fair,
explainable contribution-attribution and academic-integrity instrument**. Every
analysis request:

1. Receives a GitHub URL
2. Clones the repository into a temporary directory
3. Traverses every commit (up to 1,000), building an authored-effort event log
4. Runs a single `git blame` pass over source files to compute **line-level
   ownership** and **function-granularity code quality**
5. Runs **integrity forensics** (deadline spikes, bulk paste, authorship laundering)
6. Scores and classifies contributors (ownership-primary), with integrity flags
   carried alongside — never folded into the score
7. Deletes the clone and returns results as JSON

Results are cached in a local SQLite database keyed on `(repo_url, HEAD sha)`: an
unchanged repository is served from cache without re-cloning (the HEAD sha is
resolved up front with `git ls-remote`, no clone required). The same database
stores instructor overrides that feed the calibration report. Set
`GITSIGHT_CACHE=0` to disable caching.

> **Core principle:** reward code that *survives* (blame ownership), not code that
> was *typed* (churn). Raw lines-of-code is gameable; surviving ownership is not.

---

## Repository Structure

```
Contri/
├── backend/
│   ├── main.py          # FastAPI app — routes, middleware, server entry point
│   ├── analyzer.py      # Orchestration: clone → traverse → blame → cleanup
│   ├── attribution.py   # Line-level ownership (git blame) + authored-effort log
│   ├── quality.py       # Function-granularity quality attribution
│   ├── integrity.py     # Academic-integrity forensic signals
│   ├── explain.py       # Evidence-bound rationale per verdict
│   ├── scoring.py       # Ownership-primary impact score and role assignment
│   ├── trust/           # Trust layer (uncertainty, reliability, calibration)
│   │   ├── uncertainty.py  # Ownership confidence intervals (cluster bootstrap)
│   │   ├── reliability.py   # History-reliability scoring + evidence
│   │   ├── calibration.py   # Platt/isotonic calibration, ECE/Brier/diagrams
│   │   └── report.py        # Confidence assembly + ethical gating
│   ├── store.py         # SQLite cache, reviews, calibration models
│   ├── config.py        # All tuneable constants and environment-driven settings
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── static/
│   │   └── index.html   # Single-page React frontend
│   ├── eval/            # Evaluation harness
│   │   ├── scenarios.py # Synthetic repos (contribution + corrupted-history)
│   │   ├── metrics.py   # Role accuracy + flag precision/recall/F1
│   │   ├── runner.py    # Synthetic-set runner + CLI
│   │   ├── sensitivity.py # Threshold sweeps + false-positive curves
│   │   └── corpus.py    # Labelled real-repo manifest loader + evaluation
│   └── tests/
│       ├── test_analyzer.py
│       ├── test_attribution.py
│       ├── test_quality.py
│       ├── test_integrity.py
│       ├── test_explain.py
│       ├── test_store.py
│       ├── test_eval.py
│       └── test_scoring.py
├── .env.example
├── .gitignore
├── LICENSE              # Apache License 2.0
├── NOTICE
├── README.md
├── CONTRIBUTING.md
├── ARCHITECTURE.md   ← this file
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── ROADMAP.md
└── CHANGELOG.md
```

---

## Module Descriptions

### `main.py` — Application Entry Point

- Creates the FastAPI app with CORS middleware
- Exposes two routes: `POST /api/analyze` and `GET /health`
- Serves `static/index.html` at `GET /`
- Wraps `analyze_repository()` in `asyncio.to_thread()` so the synchronous, IO-heavy analysis does not block the uvicorn event loop
- Logs expected errors (bad URL, inaccessible repo) at WARNING level; unexpected errors at ERROR level with full traceback
- Never returns raw exception messages to callers

### `analyzer.py` — Orchestration Engine

- `validate_github_url(url)` — strict regex validation; rejects path traversal and non-GitHub URLs
- `analyze_repository(repo_url)` — clones the repo, traverses commits (building the effort event log and commit-message map), runs the ownership/quality blame pass **before cleanup**, computes integrity flags, merges authors by email, and **always deletes the clone** in a `finally` block (with `_safe_rmtree`, which clears read-only `.git` packs on Windows)
- `calculate_quality(source_code)` — legacy file-level helper retained for tests; no longer used in the main path

### `attribution.py` — Line-Level Attribution

- `build_line_ownership(repo_dir, files)` — one `git blame --line-porcelain -w -M -C` pass producing `{file: {line: email}}`; `-w/-M/-C` ignore whitespace and follow moves so reformatters/movers can't steal credit
- `ownership_from_line_map(...)` — aggregates the line map into per-author surviving-line totals
- `effort_event_from_modified_file(...)` / `aggregate_effort(...)` — per-`(commit, file)` authored-churn event log (the substrate for integrity forensics)
- `combine(ownership, effort)` — produces `ownership_pct`, `effort_pct`, and `divergence` (effort − ownership). Vendored/generated files are excluded throughout.

### `quality.py` — Function-Granularity Quality

- `attribute_quality(repo_dir, line_ownership)` — per-function cyclomatic complexity (Lizard) credited to the function's **dominant line owner**; Maintainability Index (radon, Python-only) split by ownership share
- `finalize_quality(acc)` — yields a per-author record; `assessed: false` (score `null`) when a language isn't analysable, rather than a misleading perfect score

### `integrity.py` — Academic-Integrity Forensics

Each detector returns evidence-bearing flags keyed by email; flags are advisory and **never change the impact score**.

- `detect_deadline_spike` — additions concentrated in the final slice of the timeline
- `detect_bulk_paste` — commits dwarfing the author's **median** size (robust to a single huge outlier) above an absolute floor
- `detect_authorship_laundering` — one person committing another's authored work (bot/merge committers excluded; advisory)
- `parse_co_authors` — `Co-authored-by:` trailer extraction

### `scoring.py` — Impact Score & Role Assignment

- `calculate_scores(stats)` — **ownership-primary** when attribution is present: `impact = ownership×0.55 + breadth×0.20 + effort×0.25`; falls back to the legacy churn blend when it isn't. Surfaces `ownership_pct`, `effort_pct`, `divergence`, structured `quality`, and `integrity_flags`. Roles:
  - **Major Contributor** — single author, or score ≥ 1.5× expected average
  - **Free Rider** — score ≤ 0.3× expected average
  - **Minor Contributor** — everything else

### `explain.py` — Explainability

- `build_explanation(record)` — turns a scored author into `{verdict, confidence, headline, factors, evidence, caveats, summary}`, derived deterministically from computed metrics. Optional LLM polish (`config.EXPLAIN_USE_LLM`) is constrained to the evidence and degrades to the template.
- `annotate(scored_authors)` — attaches an `explanation` to each record.

### `trust/` — Uncertainty, Reliability & Calibration

The trust layer sits *above* attribution/scoring/integrity and enforces the rule that
the system never implies certainty it lacks.

- `uncertainty.ownership_intervals` — per-author ownership confidence interval via a
  **cluster bootstrap over files** (captures file-composition variance; lines within a
  file are correlated, so files are the resampling unit). Replaces false-precision
  percentages with `"~67% (40–86%)"`.
- `reliability.assess` — scores whether the *history* supports trustworthy attribution
  (squash, rebase, mass-format, low granularity, timestamp anomalies). Score is a
  **product** `∏(1 − penalty)`, so one fatal flaw collapses it. Caps downstream confidence.
- `calibration.Calibrator` — maps the raw confidence score to an **empirically
  calibrated probability** (Platt → isotonic by label volume), with **ECE**, **Brier**,
  and **reliability-diagram** reporting. Trained from instructor reviews.
- `report.build_trust` — assembles confidence + ethical gates: low reliability caps
  confidence and raises a banner; boundary cases and unbounded ownership force caveats;
  below the floor → "insufficient — manual review required". Cold-start confidence is
  deliberately conservative (never "high" until calibrated).

### `store.py` — Persistence, Caching, Reviews & Calibration

- `get_cached` / `save_analysis` — SQLite result cache keyed on `(repo_url, HEAD sha)`
- `record_review` / `get_reviews` — instructor decisions (**confirm or correct**) — the
  unbiased label source for calibration (the old `overrides` captured disagreements only)
- `save_calibration_model` / `get_calibration_model` — persisted calibrator
- `calibration_report` — instructor-agreement stats and advisory score cutoffs

### `config.py` — Configuration

All numeric constants and environment-variable bindings live here, including ownership/quality/integrity weights and thresholds. No magic numbers exist in the other modules. To tune the algorithm, edit only this file.

---

## API Contract

### `POST /api/analyze`

**Request**

```json
{ "url": "https://github.com/owner/repo" }
```

**Response (200)**

```json
{
  "status": "success",
  "repo": "https://github.com/owner/repo",
  "total_commits": 342,
  "truncated": false,
  "authors": [
    {
      "author": "Alice",
      "score": 72.34,
      "ownership_pct": 68.1,
      "effort_pct": 64.0,
      "divergence": -4.1,
      "quality_score": 81.2,
      "quality": {
        "assessed": true,
        "quality_score": 81.2,
        "functions": 54,
        "avg_cc": 3.1,
        "complex_functions": 2,
        "maintainability": 78.4
      },
      "integrity_flags": [
        {
          "type": "deadline_spike",
          "severity": "medium",
          "score": 0.71,
          "detail": "71% of additions (820 lines) landed in the final 10% of the timeline",
          "evidence": [{ "commit": "a1b2c3d", "detail": "late commit" }]
        }
      ],
      "role": "Major Contributor",
      "stats": {
        "commits": 246,
        "lines_added": 8100,
        "lines_deleted": 1200,
        "files_modified": 310,
        "files": ["src/main.py", "..."],
        "attribution": {
          "owned_lines": 6200, "owned_files": 41,
          "effort_added": 8100, "effort_deleted": 1200, "effort_commits": 246,
          "ownership_pct": 68.1, "effort_pct": 64.0, "divergence": -4.1
        },
        "avg_quality": 81.2
      }
    }
  ],
  "timeline": [
    {
      "date": "2024-03-15",
      "timestamp": "2024-03-15T09:42:11+00:00",
      "author": "Alice",
      "insertions": 42,
      "deletions": 3,
      "msg": "feat: add login page",
      "files": ["src/login.py"]
    }
  ]
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | URL is malformed or not a GitHub URL |
| 422 | Repository is private, unreachable, or git failed |
| 500 | Unexpected server error |

The response also carries `head_sha`, `cached` (bool), and — when caching is on —
`analysis_id` (for posting overrides).

### Other endpoints

| Method & path | Purpose |
|---|---|
| `POST /api/jobs` | Start analysis in the background → `{ job_id, status }` |
| `GET /api/jobs/{id}` | Poll job status → `{ status, result? }` |
| `POST /api/override` | Record an instructor correction `{ analysis_id, author, instructor_role, note }` |
| `POST /api/review` | Record an instructor decision (confirm **or** correct) — feeds calibration |
| `GET /api/calibration?analysis_id=` | Instructor-agreement summary + advisory cutoffs |
| `POST /api/calibration/train` | Refit the confidence calibrator from reviews and persist it |
| `GET /api/calibration/metrics` | Current calibration quality (ECE, Brier, reliability diagram) |
| `GET /health` | `{ "status": "ok", "version": "1.1.0" }` |

The analyze response additionally carries a repo-level `reliability` block, and each
author carries `ownership_interval`, `boundary_case`, and an `explanation.trust`
block (`confidence`, `regime`, `probability?`, `reliability_band`, `gated`, `caveats`).

---

## Code Quality Metric (function-granularity)

Quality is attributed to the person who actually wrote the code, not everyone who
touched the file:

```
quality_score = (CC_score × 0.6) + (MI × 0.4)
```

| Sub-metric | Tool | Attribution |
|---|---|---|
| Cyclomatic Complexity (CC) | Lizard | Per **function** → credited to the function's dominant line owner. `CC_score = min(100, 100 / avg_CC)` |
| Maintainability Index (MI) | Radon (Python-only) | Per **file** → split across owners by their ownership share |

If neither signal is available for an author (unsupported language), quality is
reported as **not assessed** (`quality_score: null`) rather than a free 100.

---

## Impact Score Formula (ownership-primary)

```
impact = (ownership_pct × 0.55) + (breadth_pct × 0.20) + (effort_pct × 0.25)
```

- **ownership_pct** — share of surviving lines owned at HEAD (via `git blame`). Weighted highest because it is the least gameable signal.
- **breadth_pct** — share of owned source files.
- **effort_pct** — share of authored churn over history (captures real work later overwritten).

`divergence = effort_pct − ownership_pct` is surfaced as a signal: a large positive
value means churn that did not survive (noise, or work teammates replaced).

When attribution is unavailable, scoring falls back to the legacy churn blend
(`commit 0.30 / lines 0.50 / files 0.20`).

---

## Integrity Forensics

Advisory signals computed from the effort event log and commit metadata. They are
surfaced per author in `integrity_flags` and **never alter the impact score** — a
grader sees every signal and decides. See `integrity.py` for thresholds.

| Signal | What it catches |
|---|---|
| `deadline_spike` | Additions concentrated in the final slice of the timeline |
| `bulk_paste` | A commit far larger than the author's median (robust to single outliers) |
| `authorship_laundering` | One account committing another person's authored work |
| `co_authored_commits` | `Co-authored-by:` trailers declared on commits |

---

## Design Decisions

**Why no database?**
GitSight is an analysis tool, not a record-keeping system. Stateless operation simplifies deployment (no migrations, no persistence layer) and makes it trivially horizontally scalable.

**Why PyDriller?**
It provides a clean Pythonic API over GitPython for commit traversal, including per-file source code access — which is needed for quality analysis. The alternative (raw `git log`) would require parsing complex, edge-case-prone output.

**Why clone locally rather than using the GitHub API?**
The GitHub API rate-limits unauthenticated requests to 60/hour and does not provide file source code for every commit efficiently. Local cloning is slower but complete and API-key-free.

**Why a 1,000-commit limit?**
Traversing >1,000 commits with full file content analysis can take 10+ minutes. The limit prevents runaway requests. Repos with > 1,000 commits receive a `truncated: true` flag in the response so the UI can warn the user.

**Why not persist clone cache between requests?**
Stale clones waste disk space unpredictably and make behaviour depend on previous requests. Clean-on-exit is simpler and safer.
