"""
Threshold sensitivity analysis.

GitSight's integrity thresholds (paste floor, deadline ratio, role cutoffs, …) are
hand-chosen constants. This module quantifies how fragile each one is: it sweeps a
threshold over a grid and measures, at each value, the **detection rate** on cases
that should fire and the **false-positive rate** on an honest control set that should
not. The local slope ``d(rate)/d(threshold)`` tells you whether the chosen operating
point sits on a stable plateau or a cliff.

The detectors and scorer read their thresholds from ``config`` at call time, so a
sweep simply rebinds the constant, re-evaluates on fixed synthetic inputs, and
restores it. Inputs are synthetic and deterministic — this measures *threshold
fragility*, not real-world accuracy.

CLI:  python -m eval.sensitivity   (from backend/)
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config  # noqa: E402
from integrity import CommitAgg, detect_bulk_paste, detect_deadline_spike  # noqa: E402
from scoring import calculate_scores  # noqa: E402


def _commit(sha, author, added, ts=0.0):
    return CommitAgg(sha=sha, author_email=author, committer_email=author,
                     timestamp_utc=ts, added=added, deleted=0)


# A "paster" who should be flagged, and a clean control author who should not.
def _paste_cases() -> list[CommitAgg]:
    cs = [_commit(f"p{i}", "paster", 5, ts=float(i)) for i in range(5)]
    cs.append(_commit("paste", "paster", 600, ts=5.0))
    return cs


def _control_cases() -> list[CommitAgg]:
    # Steady, moderately-sized commits — legitimate work, no anomalies.
    return [_commit(f"c{i}", "honest", 80 + (i % 3) * 10, ts=float(i)) for i in range(8)]


def _deadline_cases() -> tuple[list[CommitAgg], list[CommitAgg]]:
    late = [_commit("e", "bob", 100, ts=10.0), _commit("late", "dumper", 200, ts=99.0)]
    control = [_commit(f"c{i}", "honest", 40, ts=float(i * 10)) for i in range(10)]
    return late, control


def _flagged_authors(detector, commits) -> set[str]:
    return set(detector(commits).keys())


def sweep(param: str, grid: list[float], evaluate) -> list[dict]:
    """Rebind ``config.<param>`` across *grid*, calling *evaluate()* at each value."""
    original = getattr(config, param)
    rows: list[dict] = []
    try:
        for value in grid:
            setattr(config, param, value)
            rows.append({"value": value, **evaluate()})
    finally:
        setattr(config, param, original)
    # Local slope of the primary rate (detection) between consecutive points.
    for i in range(1, len(rows)):
        dv = rows[i]["value"] - rows[i - 1]["value"]
        rows[i]["slope"] = round((rows[i]["detect"] - rows[i - 1]["detect"]) / dv, 4) if dv else None
    return rows


def _eval_paste() -> dict:
    detect = "paster" in _flagged_authors(detect_bulk_paste, _paste_cases())
    fp = "honest" in _flagged_authors(detect_bulk_paste, _control_cases())
    return {"detect": int(detect), "fp": int(fp)}


def _eval_deadline() -> dict:
    late, control = _deadline_cases()
    detect = "dumper" in _flagged_authors(detect_deadline_spike, late)
    fp = "honest" in _flagged_authors(detect_deadline_spike, control)
    return {"detect": int(detect), "fp": int(fp)}


def _eval_roles() -> dict:
    # Three contributors: one dominant, one mid, one negligible.
    stats = {
        "Alice": _attr_stats(70, 70, 6),
        "Bob": _attr_stats(25, 25, 3),
        "Carol": _attr_stats(5, 5, 1),
    }
    roles = [a["role"] for a in calculate_scores(stats)]
    return {"detect": roles.count("Major Contributor"), "fp": roles.count("Free Rider")}


def _attr_stats(ownership_pct, effort_pct, owned_files):
    return {
        "commits": 1, "lines_added": 1, "lines_deleted": 0, "files_modified": 1,
        "files": ["a.py"], "avg_quality": 80.0,
        "attribution": {
            "owned_lines": int(ownership_pct), "owned_files": owned_files,
            "effort_added": int(effort_pct), "effort_deleted": 0, "effort_commits": 1,
            "ownership_pct": ownership_pct, "effort_pct": effort_pct,
            "divergence": round(effort_pct - ownership_pct, 2),
        },
    }


def report() -> dict:
    return {
        "INTEGRITY_PASTE_FLOOR": sweep(
            "INTEGRITY_PASTE_FLOOR", [100, 200, 300, 400, 500, 600, 800], _eval_paste),
        "INTEGRITY_PASTE_MEDIAN_MULT": sweep(
            "INTEGRITY_PASTE_MEDIAN_MULT", [2, 3, 5, 8, 12, 20], _eval_paste),
        "INTEGRITY_DEADLINE_RATIO": sweep(
            "INTEGRITY_DEADLINE_RATIO", [0.4, 0.5, 0.6, 0.7, 0.8, 0.9], _eval_deadline),
        "ROLE_MAJOR_THRESHOLD": sweep(
            "ROLE_MAJOR_THRESHOLD", [1.1, 1.3, 1.5, 1.8, 2.2], _eval_roles),
        "ROLE_FREE_RIDER_THRESHOLD": sweep(
            "ROLE_FREE_RIDER_THRESHOLD", [0.1, 0.2, 0.3, 0.4, 0.5], _eval_roles),
    }


def main() -> None:
    print(json.dumps(report(), indent=2))


if __name__ == "__main__":
    main()
