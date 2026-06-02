"""
Function-granularity quality attribution.

The old approach ran code metrics on a *whole file* and credited the result to
*every author who touched the file* — so a student's quality grade was polluted by
code they never wrote. This module fixes the attribution:

* **Cyclomatic complexity** is measured per function (via Lizard) and credited to
  the function's *dominant owner* — the author who owns the most lines inside the
  function's line range, per the blame map.
* **Maintainability Index** (radon, Python-only) is measured per file and split
  across owners *in proportion to the lines each owns* in that file.

Where a language is not analysable, quality is reported as **not assessed** rather
than silently defaulting to a perfect score (which would reward unanalysable code).
"""

from __future__ import annotations

import logging
import os
from collections import Counter

import config

logger = logging.getLogger(__name__)

try:
    import lizard
    LIZARD_AVAILABLE = True
except ImportError:  # pragma: no cover
    LIZARD_AVAILABLE = False

try:
    import radon.metrics
    RADON_AVAILABLE = True
except ImportError:  # pragma: no cover
    RADON_AVAILABLE = False


def empty_acc() -> dict:
    return {
        "functions": 0,
        "cc_sum": 0.0,
        "high_cc": 0,
        "mi_weighted": 0.0,
        "mi_lines": 0,
    }


def merge_acc(into: dict, other: dict) -> None:
    for key in empty_acc():
        into[key] += other.get(key, 0)


def _dominant_owner(lines: dict[int, str], start: int, end: int) -> str | None:
    """Return the email owning the most lines within [start, end], or None."""
    counts = Counter(
        email for ln, email in lines.items() if start <= ln <= end
    )
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _file_mi(full_path: str) -> float | None:
    """Maintainability Index 0-100 for a Python file, or None if unavailable."""
    if not RADON_AVAILABLE or not full_path.endswith(config.MAINTAINABILITY_EXTENSIONS):
        return None
    try:
        with open(full_path, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        mi = float(radon.metrics.mi_visit(source, True))
        return max(0.0, min(100.0, mi))
    except Exception:
        return None


def attribute_quality(
    repo_dir: str, line_ownership: dict[str, dict[int, str]]
) -> dict[str, dict]:
    """
    Build a raw quality accumulator per author email from the blame line map.

    Returns {email: accumulator}; finalise each with :func:`finalize_quality`.
    """
    per_author: dict[str, dict] = {}
    if not LIZARD_AVAILABLE:
        return per_author

    for path, lines in line_ownership.items():
        full_path = os.path.join(repo_dir, path)
        if not os.path.isfile(full_path):
            continue

        # Per-function complexity → dominant owner.
        try:
            analysis = lizard.analyze_file(full_path)
            functions = analysis.function_list
        except Exception:
            functions = []

        for fn in functions:
            owner = _dominant_owner(lines, fn.start_line, fn.end_line)
            if owner is None:
                continue
            acc = per_author.setdefault(owner, empty_acc())
            acc["functions"] += 1
            acc["cc_sum"] += fn.cyclomatic_complexity
            if fn.cyclomatic_complexity > config.QUALITY_CC_HIGH_THRESHOLD:
                acc["high_cc"] += 1

        # Per-file maintainability → split by ownership share.
        mi = _file_mi(full_path)
        if mi is not None and lines:
            for email, n in Counter(lines.values()).items():
                acc = per_author.setdefault(email, empty_acc())
                acc["mi_weighted"] += mi * n
                acc["mi_lines"] += n

    return per_author


def finalize_quality(acc: dict) -> dict:
    """
    Convert a raw accumulator into a reportable quality record.

    ``assessed`` is False when no functions and no maintainability data were
    available for this author — in which case ``quality_score`` is None.
    """
    functions = acc.get("functions", 0)
    mi_lines = acc.get("mi_lines", 0)

    avg_cc: float | None = None
    cc_score: float | None = None
    if functions:
        avg_cc = acc["cc_sum"] / functions
        cc_score = max(0.0, min(100.0, (1.0 / max(avg_cc, 1.0)) * 100.0))

    mi: float | None = (acc["mi_weighted"] / mi_lines) if mi_lines else None

    if cc_score is not None and mi is not None:
        score = (
            cc_score * config.QUALITY_ATTR_WEIGHT_CC
            + mi * config.QUALITY_ATTR_WEIGHT_MI
        )
    elif cc_score is not None:
        score = cc_score
    elif mi is not None:
        score = mi
    else:
        return {
            "assessed": False,
            "quality_score": None,
            "functions": 0,
            "avg_cc": None,
            "complex_functions": 0,
            "maintainability": None,
        }

    return {
        "assessed": True,
        "quality_score": round(score, 2),
        "functions": functions,
        "avg_cc": round(avg_cc, 2) if avg_cc is not None else None,
        "complex_functions": acc.get("high_cc", 0),
        "maintainability": round(mi, 2) if mi is not None else None,
    }
