# Changelog

All notable changes to GitSight are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Changed
- **License changed from MIT to Apache License 2.0** — adds an explicit patent
  grant and trademark protection while remaining permissive. Added a `NOTICE` file.
- Contribution attribution rebuilt around **line-level ownership** (`git blame`)
  instead of raw commit churn; impact scoring is now ownership-primary.
- **Confidence is no longer a heuristic.** Ownership is reported as a confidence
  interval (`~67% (40–86%)`), not a false-precision percentage; verdict confidence is
  a conservative cold-start value (never "high" until calibrated) or, once instructor
  reviews exist, an empirically calibrated probability. Low repository reliability
  caps confidence and raises a banner.

### Added (trust layer — D1)
- `trust/uncertainty.py` — ownership confidence intervals via cluster bootstrap over files.
- `trust/reliability.py` — history-reliability scoring (squash, rebase, mass-format,
  low granularity, timestamp anomalies) with an evidence chain; gates confidence.
- `trust/calibration.py` — Platt/isotonic confidence calibration with ECE, Brier, and
  reliability-diagram reporting (bootstrap CIs).
- `trust/report.py` — confidence assembly + ethical gating (boundary cases, insufficient
  evidence → "manual review required").
- `reviews` + `calibration_models` tables; `POST /api/review` (confirm or correct),
  `POST /api/calibration/train`, `GET /api/calibration/metrics`.
- `eval/sensitivity.py` — threshold-sweep / false-positive curves (`python -m eval.sensitivity`).
- Repo-level `reliability` and per-author `ownership_interval` / `boundary_case` /
  `explanation.trust` in the API response; frontend reliability banner, ownership
  intervals, confidence regime, and Agree/Correct review controls.

### Added
- `attribution.py` — surviving-line ownership (blame) + diff-parsed effort log,
  with vendored/generated-file exclusion so dependencies cannot inflate a score.
- Per-author `ownership_pct`, `effort_pct`, and `divergence` in the API response.
- `quality.py` — **function-granularity** quality attribution (complexity credited
  to the function's dominant owner); unanalysable languages report "not assessed".
- `integrity.py` — academic-integrity forensics: deadline spikes, bulk paste
  (robust median test), authorship laundering, co-author trailers. Flags are
  surfaced alongside the verdict, never folded into the score.
- `explain.py` — evidence-bound, confidence-rated rationale for every verdict.
- `store.py` — SQLite result **cache** keyed on `(repo_url, HEAD sha)`, instructor
  **overrides**, and a **calibration** report (agreement + advisory cutoffs).
- New endpoints: `POST /api/jobs` + `GET /api/jobs/{id}` (background analysis),
  `POST /api/override`, `GET /api/calibration`.
- Frontend surfaces ownership/effort/divergence, per-author integrity signals,
  the rationale, an instructor-override control, and a "cached" indicator.
- `eval/` evaluation harness — synthetic repos with injected ground truth and
  role-accuracy / flag precision-recall metrics (`python -m eval.runner`).
- `eval/corpus.py` — labelled real-repository corpus framework: manifest schema,
  loader, validation, and evaluation (`python -m eval.corpus <manifest.json>`),
  with an annotation guide (`eval/corpus/README.md`). No labelled data ships.
- `analyze_repository(url, deadline=…)` — optional real deadline to sharpen the
  deadline-spike signal instead of inferring it from the last commit.
- `LIMITATIONS.md` documenting known caveats across attribution, quality,
  integrity, scale, and evaluation.

### Fixed
- Clone cleanup now actually runs on Windows (read-only `.git` packs are handled);
  the previous `rmtree(ignore_errors=True)` silently failed, defeating the
  disk-growth guard.

---

## [1.0.0] — 2025

### Added
- Deep git commit traversal via PyDriller (up to 1,000 commits per repo)
- Per-author Impact Score: weighted composite of commits (30%), lines changed (50%), and files touched (20%)
- Per-author Code Quality Score from five sub-metrics:
  - Cyclomatic Complexity via Lizard (35%)
  - Maintainability Index via Radon (25%)
  - Comment Density (15%)
  - Linter heuristic — penalises lines > 100 chars (15%)
  - Readability — penalises high average line length (10%)
- Role classification: Major Contributor, Minor Contributor, Free Rider
- Author deduplication by email — merges contributions from same person using different display names
- Sole-contributor edge case: single author always classified as Major Contributor
- Commit timeline with date, insertions, deletions, and files per commit
- Dark-mode React SPA dashboard (Tailwind CSS + Chart.js doughnut)
- Expandable contributor rows with files modified and commit history
- Free-rider alert panel when imbalance is detected
- CSV export of analysis results
- Example repository URL chips on landing page
- Inline error display (replaced browser `alert()`)
- Keyboard-accessible contributor rows (`role="button"`, `tabIndex`, `onKeyDown`)
- Role badges with icons and semantic colour coding (emerald / amber / rose)
- Screen-reader-accessible chart data table (visually hidden)
- `GET /health` endpoint
- `truncated: true` flag in API response when commit limit is reached
- Strict GitHub URL validation via regex (closes path-traversal surface)
- Clone cleanup via `try/finally` — no unbounded disk growth
- Structured logging throughout the backend
- `asyncio.to_thread()` wrapper — analysis no longer blocks the event loop
- `config.py` — all tuneable constants and environment-variable bindings in one place
- `requirements.txt` and `requirements-dev.txt` with pinned versions
- Pinned CDN library versions in `index.html` (no more `@latest`)
- MIT License
- `.gitignore` (excludes `.cache/`, `venv/`, `__pycache__/`, etc.)
- `.env.example`
- `CONTRIBUTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- `ROADMAP.md`, `CHANGELOG.md`
- `.github/` issue templates and pull request template
- GitHub Actions CI workflow: lint (ruff) + tests (pytest) + Docker build
- `Dockerfile` and `docker-compose.yml`
- Backend test suite: 20 tests covering URL validation, quality scoring, and role assignment

### Fixed
- `cc_score` math bug — cyclomatic complexity score is now clamped to 0–100 (previously could exceed 1,000)
- Sole contributor role — was incorrectly classified as Minor Contributor; now correctly Major Contributor
- CORS misconfiguration — `allow_credentials=True` with wildcard origin is now corrected
- Internal error details no longer exposed in HTTP 500 responses
- Bare `except:` clauses replaced with `except Exception:` throughout
- API URL detection — removed fragile port-5500 check; now always uses relative `/api/analyze`

[Unreleased]: https://github.com/Manas-Maahir/GitSight/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Manas-Maahir/GitSight/releases/tag/v1.0.0
