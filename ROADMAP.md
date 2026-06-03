# Roadmap

This document describes the planned direction for GitSight. It is a living document — priorities may shift based on community feedback.

---

## Released

### v1.0 — Foundation
- Deep git history analysis via PyDriller
- Impact Score (commits 30%, lines 50%, files 20%)
- Code Quality Score (cyclomatic complexity, maintainability index, comment density, linter, readability)
- Role classification: Major Contributor, Minor Contributor, Free Rider
- Author deduplication by email
- Dark-mode single-page dashboard (React + Tailwind)
- Commit timeline per author
- CSV export
- `/health` endpoint
- Apache-2.0 license, full open-source documentation

---

## In Progress

### v1.1 — Educator Workflow
- [ ] **Date range filter** — Analyse commits within a specific date range (e.g., sprint, semester)
- [ ] **Truncation warning** — Surface a clear notice when repositories exceed the 1,000-commit limit

---

## Research & Evaluation

- [x] **Uncertainty-aware attribution & confidence calibration (D1)** — ownership
  confidence intervals (cluster bootstrap), history-reliability scoring, conservative
  cold-start confidence, instructor-review calibration (Platt/isotonic) with ECE/Brier/
  reliability diagrams, ethical gating, and a threshold-sensitivity framework
  (`backend/trust/`, `python -m eval.sensitivity`). See [LIMITATIONS.md](LIMITATIONS.md)
  for what remains in-sample/heuristic.
- [x] **Evaluation harness** — synthetic repos with injected ground truth; role
  accuracy + integrity-flag precision/recall/F1 (`backend/eval/`, `python -m eval.runner`)
- [ ] **Held-out calibration evaluation** — cross-validated ECE on a real labelled
  corpus (current ECE is in-sample/optimistic)
- [~] **Labelled real-world corpus** — manifest schema, loader, validation, and
  evaluation shipped (`backend/eval/corpus.py`, `python -m eval.corpus`); the
  labelled dataset itself is human-annotation work (see `eval/corpus/README.md`).
  Real-deadline support is threaded through `analyze_repository(url, deadline=…)`.
- [ ] **AI-generated-code signal** — advisory-only, after a reliable method exists

---

## Planned

### v1.2 — Analysis Quality
- [ ] **Configurable scoring weights** — Allow callers to override commit/lines/files weights via API parameters
- [ ] **Bulk copy-paste detection** — Flag single commits with unusually large line additions relative to the author's history
- [ ] **Language breakdown** — Show which file types each author contributed to (Python, JS, CSS, etc.)
- [ ] **Commit spike detection** — Identify last-minute contribution spikes before deadlines

### v1.3 — Sharing & Persistence
- [ ] **Shareable report links** — Generate a UUID-based permalink to cached analysis results (SQLite backend)
- [ ] **Analysis history** — Store and retrieve past analyses without re-cloning
- [ ] **Team comparison** — Compare two repositories or two contributors side by side

### v1.4 — Scale & Performance
- [x] **Result caching** — SQLite cache keyed on `(repo_url, HEAD_sha)`; HEAD resolved via `git ls-remote` with no clone
- [~] **Background task queue** — in-process async jobs (`/api/jobs`) shipped; Celery/RQ for multi-worker still planned
- [ ] **Progress streaming** — Server-sent events (SSE) for real-time clone/traversal progress (analyzer not yet instrumented to emit progress)

### v2.0 — Platform
- [ ] **GitHub OAuth** — Analyse private repositories with user consent
- [ ] **Classroom management** — Group multiple repos into an "assignment" for batch analysis
- [ ] **LMS integration** — Export results to Canvas, Moodle, or Google Classroom
- [ ] **Anonymous reporting** — Generate reports where contributor names are pseudonymised
- [ ] **GitLab / Bitbucket support** — Extend analysis to non-GitHub hosts

---

## Ideas Under Consideration

- Multilingual UI (i18n)
- Institutional branding / white-label
- Webhook-triggered analysis on push
- VS Code extension

---

## Contributing to the Roadmap

Have a feature request? Open a [Feature Request issue](https://github.com/Manas-Maahir/GitSight/issues/new?template=feature_request.md). Upvoted issues inform prioritisation.
