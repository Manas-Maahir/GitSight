"""
Attribution reliability scoring.

Estimates whether a repository's *history* can support trustworthy line-level
attribution. Some workflows silently corrupt blame-based ownership:

* **squash merges** collapse many people's work onto the merger,
* **rebases / force-pushes** rewrite authorship metadata and timestamps,
* **mass-formatting commits** reattribute whole files to a reformatter,
* **coarse history** (few large commits) leaves ownership under-determined,
* **timestamp anomalies** indicate rewritten or fabricated history.

Each detector returns a penalty in ``[0, cap]`` with evidence. The reliability score
is the **product** ``∏ (1 − penalty)`` — deliberately, so a single disqualifying flaw
collapses the score rather than being averaged away by healthy signals.

This detection is itself heuristic: it flags *risk*, never certainty. A high score is
not proof of clean history, and a low score is a prompt for human review, not an
accusation. Reliability caps downstream confidence and drives the ethical gate.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import config

# GitHub squash-merge default titles end with "(#123)"; classic merges start with
# "Merge pull request".
_SQUASH_RE = re.compile(r"\(#\d+\)\s*$")
_MERGE_RE = re.compile(r"^Merge pull request #\d+", re.IGNORECASE)


@dataclass
class ReliabilityReport:
    score: float
    band: str
    factors: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "band": self.band,
            "factors": self.factors,
            "evidence": self.evidence[:20],
        }


def _band(score: float) -> str:
    if score >= config.TRUST_BAND_HIGH:
        return "high"
    if score >= config.TRUST_BAND_MODERATE:
        return "moderate"
    if score >= config.TRUST_BAND_LOW:
        return "low"
    return "unreliable"


def detect_squash(commits: list[dict]) -> tuple[float, dict | None, list[dict]]:
    if not commits:
        return 0.0, None, []
    hits = [c for c in commits
            if _SQUASH_RE.search((c.get("msg") or "").splitlines()[0] if c.get("msg") else "")
            or _MERGE_RE.search(c.get("msg") or "")]
    ratio = len(hits) / len(commits)
    penalty = min(config.TRUST_SQUASH_PENALTY_CAP,
                  ratio / config.TRUST_SQUASH_RATIO_FULL * config.TRUST_SQUASH_PENALTY_CAP)
    if penalty <= 0:
        return 0.0, None, []
    factor = {
        "signal": "squash_merges",
        "penalty": round(penalty, 3),
        "detail": f"{len(hits)}/{len(commits)} commits look like squash/PR merges — "
                  "authorship may be collapsed onto the merger",
    }
    evidence = [{"commit": c["sha"], "detail": "squash/merge pattern"} for c in hits[:10]]
    return penalty, factor, evidence


def detect_rebase(commits: list[dict]) -> tuple[float, dict | None, list[dict]]:
    if not commits:
        return 0.0, None, []
    gapped = [c for c in commits
              if (c.get("committer_ts") or 0) - (c.get("author_ts") or 0)
              > config.TRUST_REBASE_GAP_SECONDS]
    ratio = len(gapped) / len(commits)
    penalty = min(config.TRUST_REBASE_PENALTY_CAP,
                  ratio / config.TRUST_REBASE_RATIO_FULL * config.TRUST_REBASE_PENALTY_CAP)
    if penalty <= 0:
        return 0.0, None, []
    factor = {
        "signal": "rebase_or_amend",
        "penalty": round(penalty, 3),
        "detail": f"{len(gapped)}/{len(commits)} commits have committer dates well after "
                  "their author dates — history was likely rebased or amended",
    }
    evidence = [{"commit": c["sha"], "detail": "committer≫author date"} for c in gapped[:10]]
    return penalty, factor, evidence


def detect_format_bombs(commits: list[dict]) -> tuple[float, dict | None, list[dict]]:
    bombs = []
    for c in commits:
        added, deleted, files = c.get("added", 0), c.get("deleted", 0), c.get("files", 0)
        churn = added + deleted
        balanced = deleted > 0 and 0.5 <= added / max(deleted, 1) <= 2.0
        if files >= config.TRUST_FORMAT_FILES and churn >= config.TRUST_FORMAT_CHURN and balanced:
            bombs.append(c)
    penalty = min(config.TRUST_FORMAT_PENALTY_CAP,
                  len(bombs) * config.TRUST_FORMAT_PENALTY_PER)
    if penalty <= 0:
        return 0.0, None, []
    factor = {
        "signal": "mass_formatting",
        "penalty": round(penalty, 3),
        "detail": f"{len(bombs)} commit(s) reformat many files at once — these reattribute "
                  "whole files to the reformatter",
    }
    evidence = [{"commit": c["sha"], "detail": f"{c.get('files')} files, {c.get('added', 0) + c.get('deleted', 0)} churn"}
                for c in bombs[:10]]
    return penalty, factor, evidence


def detect_low_granularity(commits: list[dict]) -> tuple[float, dict | None, list[dict]]:
    total = len(commits)
    if total == 0:
        return 0.0, None, []
    penalty = 0.0
    detail = None
    if total < config.TRUST_LOW_COMMITS:
        penalty = (config.TRUST_LOW_COMMITS - total) / config.TRUST_LOW_COMMITS \
            * config.TRUST_GRANULARITY_PENALTY_CAP
        detail = f"only {total} commit(s) — too coarse to localise ownership reliably"
    if penalty <= 0:
        return 0.0, None, []
    factor = {"signal": "low_granularity", "penalty": round(penalty, 3), "detail": detail}
    return penalty, factor, []


def detect_timestamp_anomalies(commits: list[dict]) -> tuple[float, dict | None, list[dict]]:
    if not commits:
        return 0.0, None, []
    now = time.time()
    anomalous = []
    for c in commits:
        a, k = c.get("author_ts") or 0, c.get("committer_ts") or 0
        if a > now + 86400 or k > now + 86400 or a <= 0 or k <= 0:
            anomalous.append(c)
    ratio = len(anomalous) / len(commits)
    penalty = min(config.TRUST_TIMESTAMP_PENALTY_CAP, ratio * config.TRUST_TIMESTAMP_PENALTY_CAP * 2)
    if penalty <= 0:
        return 0.0, None, []
    factor = {
        "signal": "timestamp_anomalies",
        "penalty": round(penalty, 3),
        "detail": f"{len(anomalous)}/{len(commits)} commits have impossible timestamps "
                  "(future or zero) — history may be fabricated",
    }
    evidence = [{"commit": c["sha"], "detail": "bad timestamp"} for c in anomalous[:10]]
    return penalty, factor, evidence


_DETECTORS = (
    detect_squash,
    detect_rebase,
    detect_format_bombs,
    detect_low_granularity,
    detect_timestamp_anomalies,
)


def assess(commits: list[dict]) -> ReliabilityReport:
    """Compose all detectors into a reliability report. ``commits`` is a list of dicts:
    {sha, author_email, committer_email, author_ts, committer_ts, msg, added, deleted, files}."""
    score = 1.0
    factors: list[dict] = []
    evidence: list[dict] = []
    for detector in _DETECTORS:
        penalty, factor, ev = detector(commits)
        if factor:
            score *= (1 - penalty)
            factors.append(factor)
            evidence.extend(ev)
    return ReliabilityReport(score=score, band=_band(score), factors=factors, evidence=evidence)
