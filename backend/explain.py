"""
Explainability layer.

Turns a scored author record into an evidence-bound, appeal-proof rationale: a
structured object plus plain-language prose. Every statement is derived
deterministically from already-computed metrics — the narrator never invents
facts. This is what makes a verdict defensible in a grading dispute.

An optional LLM polish step (``config.EXPLAIN_USE_LLM``) may rewrite the
deterministic bullets into smoother prose, but it is constrained to the evidence
and always degrades gracefully back to the template.
"""

from __future__ import annotations

import config
from trust import report

_FLAG_LABELS = {
    "deadline_spike": "Deadline spike",
    "bulk_paste": "Bulk paste",
    "authorship_laundering": "Authorship laundering",
    "co_authored_commits": "Co-authored commits",
}

_ATTRIBUTION_CAVEAT = (
    "Ownership reflects surviving lines at HEAD; large refactors or rewrites by "
    "others can shift attribution."
)


def build_explanation(record: dict, reliability: dict | None = None, calibrator=None) -> dict:
    """
    Build a structured rationale for one scored author record.

    Returns: {verdict, confidence, regime, headline, factors[], evidence[],
              caveats[], summary, trust}
    """
    role = record.get("role", "Minor Contributor")
    own = record.get("ownership_pct")
    interval = record.get("ownership_interval")
    div = record.get("divergence")
    quality = record.get("quality") or {}
    flags = record.get("integrity_flags") or []
    stats = record.get("stats") or {}
    attr = stats.get("attribution") or {}
    owned_files = attr.get("owned_files", 0)

    ownership_text = report.format_ownership(interval, own)

    factors: list[dict] = []
    evidence: list[dict] = []
    caveats: list[str] = []

    # 1. Ownership — the primary factor (reported as an interval, never false precision).
    if own is not None:
        factors.append({
            "label": "Code ownership",
            "detail": f"Owns {ownership_text} of surviving code across {owned_files} file(s).",
            "direction": "positive" if own >= 20 else "negative" if own < 5 else "neutral",
        })

    # 2. Divergence between effort and ownership.
    if div is not None and div >= config.EXPLAIN_DIVERGENCE_NOTE:
        factors.append({
            "label": "Churn did not survive",
            "detail": (
                f"Authored {div} percentage points more churn than they ultimately own — "
                "much of their added code was later replaced."
            ),
            "direction": "negative",
        })
    elif div is not None and div <= -config.EXPLAIN_DIVERGENCE_NOTE:
        factors.append({
            "label": "Stable authorship",
            "detail": "Owns considerably more surviving code than their raw churn would suggest.",
            "direction": "positive",
        })

    # 3. Quality.
    if quality.get("assessed"):
        qs = quality.get("quality_score")
        if qs is not None and qs < config.EXPLAIN_QUALITY_LOW:
            factors.append({
                "label": "Low code quality",
                "detail": f"Attributed quality {qs} (avg complexity {quality.get('avg_cc')}).",
                "direction": "negative",
            })
    else:
        caveats.append(
            "Code quality not assessed (no analysable source attributed to this author)."
        )

    # 4. Integrity flags — surfaced as factors, with their evidence collected.
    for flag in flags:
        factors.append({
            "label": _FLAG_LABELS.get(flag["type"], flag["type"]),
            "detail": flag.get("detail", ""),
            "direction": "flag",
            "severity": flag.get("severity", "advisory"),
        })
        for ev in (flag.get("evidence") or [])[:5]:
            evidence.append(ev)

    caveats.append(_ATTRIBUTION_CAVEAT)

    # Confidence + ethical gating come from the trust layer (uncertainty + reliability
    # + boundary), not a heuristic. Cold-start confidence is deliberately conservative.
    trust = report.build_trust(record, reliability, calibrator)
    caveats = trust["caveats"] + caveats

    headline = _headline(role, ownership_text, owned_files)
    summary = _render_summary(headline, factors, caveats)

    explanation = {
        "verdict": role,
        "confidence": trust["confidence"],
        "regime": trust["regime"],
        "headline": headline,
        "factors": factors,
        "evidence": evidence,
        "caveats": caveats,
        "summary": summary,
        "trust": trust,
    }

    if config.EXPLAIN_USE_LLM:
        explanation["summary"] = _llm_polish(explanation)

    return explanation


def _headline(role: str, ownership_text: str, owned_files: int) -> str:
    if "Major" in role:
        return f"Marked Major Contributor: owns {ownership_text} of surviving code across {owned_files} file(s)."
    if "Free" in role:
        return f"Marked Free Rider: owns only {ownership_text} of surviving code."
    return f"Marked Minor Contributor: owns {ownership_text} of surviving code."


def _render_summary(headline: str, factors: list[dict], caveats: list[str]) -> str:
    parts = [headline]
    flag_factors = [f for f in factors if f.get("direction") == "flag"]
    detail_factors = [f for f in factors if f.get("direction") != "flag"][1:3]
    for f in detail_factors:
        parts.append(f["detail"])
    if flag_factors:
        labels = ", ".join(f["label"].lower() for f in flag_factors)
        parts.append(f"Integrity signals raised: {labels} (advisory — review the evidence).")
    return " ".join(parts)


def _llm_polish(explanation: dict) -> str:  # pragma: no cover - optional, network-bound
    """Placeholder for an LLM rewrite constrained to the evidence; falls back to template."""
    try:
        # Intentionally not wired to a provider here. A real implementation would
        # pass `explanation` (and nothing else) to the model and return prose.
        raise NotImplementedError
    except Exception:
        return explanation["summary"]


def annotate(scored_authors: list[dict], reliability: dict | None = None,
             calibrator=None) -> list[dict]:
    """Attach an ``explanation`` to each scored author record (in place) and return it."""
    for record in scored_authors:
        record["explanation"] = build_explanation(record, reliability, calibrator)
    return scored_authors
