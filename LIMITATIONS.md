# Limitations & Known Caveats

GitSight is an analysis instrument, not an oracle. Its verdicts are **evidence to
inform a human grader, never an automated judgement**. This document records the
known limits honestly so results are interpreted correctly. Each item links to the
roadmap where a mitigation is planned.

## Attribution

- **Blame is not laundering-proof.** Ownership uses `git blame -w -M -C`, which
  ignores whitespace and follows moves/copies — but it cannot fully defeat a
  determined launderer (reformat-then-recommit, squash merges that collapse
  authorship, or rewriting history). Treat ownership as a strong signal, not proof.
- **Surviving-line bias.** Ownership counts lines that survive at HEAD. A student
  who wrote correct code later replaced by a teammate's refactor loses ownership for
  legitimate work. The `effort_pct` / `divergence` signals exist to surface this, but
  reviewers must read them together, not ownership alone.
- **Squashed / rebased histories** collapse or rewrite authorship and degrade every
  downstream signal. There is currently no detection or warning for this.

## Code quality

- **Language coverage is limited.** Cyclomatic complexity comes from Lizard
  (a fixed language set); Maintainability Index is **Python-only** (radon). For
  unsupported languages, quality is reported as **not assessed** — never a free 100,
  but also no signal.
- **Function-owner attribution is approximate.** A function is credited to its
  *dominant* line owner; mixed-authorship functions attribute wholesale to one person.

## Integrity forensics (all signals are advisory)

- **Timing forensics needs the real deadline.** `deadline_spike` infers the deadline
  from the last commit when none is supplied; a supplied deadline makes it far stronger.
- **Authorship laundering is noisy and partial.** `committer ≠ author` is often
  legitimate (rebases, merges). It is flagged advisory-only, and it only surfaces for
  a person who *also* authored code (a committer who never authors is not yet attributed).
- **AI-generated-code detection is not implemented.** It was deliberately deferred:
  current detectors are unreliable and risk false accusations. (Roadmap, advisory-only.)
- **Internal copy-paste detection is shallow.** `bulk_paste` flags anomalously large
  commits; it does not yet match pasted blocks against existing repo content.

## Scale & operations

- **Background jobs are in-process.** `/api/jobs` uses an in-memory registry: jobs do
  not survive a restart and are not shared across workers. Multi-worker deployments
  need Celery/RQ (roadmap).
- **No progress streaming yet.** The analyzer is not instrumented to emit progress, so
  long analyses show only a spinner. SSE is planned.
- **Cache has no eviction.** Entries are keyed by HEAD sha (so they self-invalidate on
  new commits), but stale shas accumulate. A size/age cap is a small follow-up.
- **1,000-commit limit.** Larger repos are truncated (flagged `truncated: true`),
  which can skew attribution on very large histories.

## Uncertainty & confidence

- **Ownership intervals capture file-composition variance only.** The cluster bootstrap
  over files quantifies how fragile an estimate is to which files exist — it does **not**
  capture blame-method error (moves, reformatting, squash). That error is the job of the
  reliability score, which is itself heuristic. Read the interval and the reliability
  band together, never the interval alone.
- **Reliability detection is heuristic.** Squash/rebase/format detection flags *risk*,
  not certainty: it can miss a cleverly rewritten history (false reassurance) or flag a
  legitimate one (e.g., a sanctioned bulk reformat). A high reliability score is not a
  clean bill of health.
- **Cold-start confidence is deliberately under-confident**, not calibrated. Until a
  calibration model is trained it never reads "high" — this is a safety choice, not a
  measurement.

## Calibration

- **Reported calibration metrics are in-sample.** ECE/Brier/reliability-diagram from
  `GET /api/calibration/metrics` are computed on the same reviews the model was fit on,
  so they are **optimistic**. A held-out (or cross-validated) evaluation on a larger
  label set is required before any calibration claim is defensible; with few labels the
  metrics are noisy (hence the bootstrap CI on ECE).
- **Calibration is corruptible.** If instructors rubber-stamp "Agree" without genuine
  review, the labels — and therefore the calibrated probabilities — become meaningless.
- **Calibration only adjusts confidence, never the score or thresholds.** It does not
  silently re-weight scoring; auto-applying learned weights would make a verdict
  unappealable, contradicting the transparency goal. `calibration_report` still only
  *suggests* cutoffs.

## Evaluation

- **The evaluation harness uses synthetic repos.** `backend/eval/scenarios.py`
  validates the detectors against repos with injected, known-ground-truth behaviour.
  This proves the signals fire as designed but is **not** a substitute for evaluation
  on real projects.
- **A real-corpus framework exists, but no labelled data ships.**
  `backend/eval/corpus.py` can ingest and score a manifest of real repositories with
  human-assigned labels, but populating it with a defensible, labelled dataset of real
  student projects is human annotation work that has not been done. Until it is,
  accuracy claims rest on synthetic evidence only.

---

See [ROADMAP.md](ROADMAP.md) for planned mitigations and [ARCHITECTURE.md](ARCHITECTURE.md)
for how each signal is computed.
