"""
Uncertainty-aware ownership.

Blame at HEAD is deterministic, so ownership has no classical sampling noise. The
honest, defensible uncertainty is **estimator sensitivity to file composition**: if an
author's ownership rides on one large file, the estimate is fragile. Because lines
within a file are highly correlated (an author owns long runs of lines), a line-level
bootstrap would fabricate absurdly tight intervals — false precision. The correct
resampling unit is the **file (cluster)**.

This module turns the precomputed ``line_ownership`` map (``{file: {line: author}}``)
into per-author ownership intervals via a **cluster bootstrap over files**. It is cheap
(operates on counts; no re-blame) and assumption-light.

Scope caveat (must be surfaced): the interval captures *file-composition* uncertainty,
**not** blame-method error (moves, reformatting, squash). Method error is the job of the
reliability layer.
"""

from __future__ import annotations

import random
from collections import Counter

import config


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in [0, 100]) on a pre-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (q / 100.0) * (len(sorted_values) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _file_counts(line_ownership: dict[str, dict[int, str]]) -> tuple[list[str], list[Counter]]:
    """Reduce the line map to per-file author counts (drops empty files)."""
    files: list[str] = []
    counts: list[Counter] = []
    for path, lines in line_ownership.items():
        if not lines:
            continue
        files.append(path)
        counts.append(Counter(lines.values()))
    return files, counts


def ownership_intervals(
    line_ownership: dict[str, dict[int, str]],
    samples: int | None = None,
    ci: float | None = None,
    seed: int | None = None,
) -> dict[str, dict]:
    """
    Return per-author ownership point estimate + confidence interval.

    Output: {author: {point, lo, hi, ci_width, n_files, insufficient}} with all
    percentages on a 0–100 scale. ``insufficient`` is True when there are too few
    files to bound ownership, in which case the interval is the full [0, 100].
    """
    samples = samples or config.TRUST_BOOTSTRAP_SAMPLES
    ci = ci if ci is not None else config.TRUST_CI
    seed = seed if seed is not None else config.TRUST_BOOTSTRAP_SEED

    files, counts = _file_counts(line_ownership)
    authors = set().union(*counts) if counts else set()
    if not authors:
        return {}

    # Point estimate: true repo-wide share.
    total_owned: Counter = Counter()
    for c in counts:
        total_owned.update(c)
    grand_total = sum(total_owned.values()) or 1
    n_files_by_author = {a: sum(1 for c in counts if c.get(a)) for a in authors}

    lower_q = (1 - ci) / 2 * 100
    upper_q = (1 + ci) / 2 * 100

    # Too few files: ownership cannot be bounded — report the full range honestly.
    if len(files) < config.TRUST_MIN_FILES_FOR_CI:
        return {
            a: {
                "point": round(total_owned[a] / grand_total * 100, 1),
                "lo": 0.0,
                "hi": 100.0,
                "ci_width": 100.0,
                "n_files": n_files_by_author[a],
                "insufficient": True,
            }
            for a in authors
        }

    rng = random.Random(seed)
    n = len(files)
    shares: dict[str, list[float]] = {a: [] for a in authors}
    for _ in range(samples):
        sample_idx = [rng.randrange(n) for _ in range(n)]
        agg: Counter = Counter()
        for i in sample_idx:
            agg.update(counts[i])
        tot = sum(agg.values()) or 1
        for a in authors:
            shares[a].append(agg.get(a, 0) / tot * 100)

    result: dict[str, dict] = {}
    for a in authors:
        s = sorted(shares[a])
        lo = round(_percentile(s, lower_q), 1)
        hi = round(_percentile(s, upper_q), 1)
        result[a] = {
            "point": round(total_owned[a] / grand_total * 100, 1),
            "lo": lo,
            "hi": hi,
            "ci_width": round(hi - lo, 1),
            "n_files": n_files_by_author[a],
            "insufficient": False,
        }
    return result
