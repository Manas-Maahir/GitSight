# Evaluation Harness

This package measures whether GitSight's attribution, scoring, and integrity
signals actually do what they claim — not just that the code runs.

## What it does

`scenarios.py` builds throwaway git repositories that inject **known, labelled
behaviour** (a free rider, a deadline dump, a bulk paste, authorship laundering).
`runner.py` runs the full pipeline (`analyze_repository` → `calculate_scores` →
integrity flags) over each repo and compares the predictions against the injected
ground truth. `metrics.py` computes role accuracy and flag precision/recall/F1.

## Running

From the `backend/` directory:

```bash
python -m eval.runner
```

This prints a per-scenario and overall report. The unit test `tests/test_eval.py`
runs the same harness and asserts the detectors hit their targets.

## Methodology & reproducibility

- **Deterministic.** Commit timestamps are fixed relative to a constant base date,
  so runs do not depend on wall-clock time. Author identities and content sizes are
  fixed, with deliberately clear separation to avoid borderline verdicts.
- **Isolation.** Each scenario is designed to exercise one signal without tripping
  the others (e.g., the deadline dump is spread across several medium commits so it
  does not also look like a bulk paste).
- **Per-signal metrics.** Flag evaluation is over `(author, flag_type)` pairs:
  true positives are correctly-fired flags, false positives are spurious flags,
  false negatives are missed injections.

## Honest scope

These are **synthetic** repos. Perfect scores here demonstrate the detectors behave
as designed on controlled inputs; they are **not** evidence of accuracy on real
student projects. A labelled corpus of real group repositories is the next step
(see [ROADMAP.md](../../ROADMAP.md) and [LIMITATIONS.md](../../LIMITATIONS.md)).

## Adding a scenario

1. Write a builder in `scenarios.py` returning `(repo_path, GroundTruth)` via `_finish`.
2. Add it to `DEFAULT_SCENARIOS`.
3. Add an assertion in `tests/test_eval.py`.
