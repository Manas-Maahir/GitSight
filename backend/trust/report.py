"""
Trust report assembly.

Combines per-author uncertainty (ownership interval), repo-level reliability, and
role-boundary fragility into a single, conservative confidence judgement plus the
caveats that must travel with a verdict. This is the enforcement point for the
project's core rule: **never imply certainty the system does not have.**

Until a calibration model exists (Phase E), confidence is **cold-start**: a
deliberately under-confident value derived by uncertainty propagation, capped so it
can never read "high" without empirical backing. Low reliability caps it further and
raises a banner; boundary cases and unbounded ownership force explicit caveats.
"""

from __future__ import annotations

import config

_LADDER = ["insufficient", "low", "moderate", "high"]


def _cap(band: str, ceiling: str) -> str:
    return _LADDER[min(_LADDER.index(band), _LADDER.index(ceiling))]


def _cold_start_value(reliability_score: float, interval: dict | None,
                      boundary: bool, insufficient: bool) -> float:
    # Ownership that cannot be bounded → no automated confidence at all.
    if insufficient or interval is None:
        return 0.0
    ci_width = interval["ci_width"]
    width_factor = max(0.0, 1 - ci_width / 100.0)
    value = reliability_score * width_factor
    if boundary:
        value *= 0.5
    return value


def _band_from_value(value: float) -> str:
    if value < config.TRUST_CONFIDENCE_FLOOR:
        return "insufficient"
    if value < config.TRUST_CONF_MODERATE:
        return "low"
    return "moderate"   # cold-start ceiling — "high" requires calibration


def _band_from_probability(p: float) -> str:
    if p >= config.TRUST_CALIB_BAND_HIGH:
        return "high"
    if p >= config.TRUST_CALIB_BAND_MODERATE:
        return "moderate"
    if p >= config.TRUST_CALIB_BAND_LOW:
        return "low"
    return "insufficient"


def build_trust(record: dict, reliability: dict | None = None, calibrator=None) -> dict:
    """Return the trust block for one scored author record.

    If a ready *calibrator* is supplied, confidence is an empirically calibrated
    probability (regime "calibrated", "high" permitted); otherwise it is the
    deliberately conservative cold-start value (capped at "moderate").
    """
    interval = record.get("ownership_interval")
    insufficient = bool(interval and interval.get("insufficient"))
    boundary = bool(record.get("boundary_case"))
    rel = reliability or {}
    rel_score = rel.get("score", 1.0)
    rel_band = rel.get("band", "high")

    value = _cold_start_value(rel_score, interval, boundary, insufficient)
    caveats: list[str] = []
    gated = False
    probability = None

    if calibrator is not None and getattr(calibrator, "ready", False):
        probability = calibrator.predict(value)
        regime = "calibrated"
        band = _band_from_probability(probability)
    else:
        regime = "cold-start"
        band = _band_from_value(value)

    # Ethical gate: unreliable history caps confidence and warns explicitly.
    if rel_score < config.TRUST_RELIABILITY_FLOOR:
        band = _cap(band, "low")
        gated = True
        reasons = ", ".join(
            f["signal"].replace("_", " ") for f in rel.get("factors", [])
        ) or "unreliable history"
        caveats.append(
            f"Repository history may be unreliable ({reasons}); attribution is low-confidence."
        )

    if band == "insufficient":
        caveats.append("Insufficient evidence for an automated verdict — manual review required.")
    if boundary:
        caveats.append("This verdict sits near a role threshold and could go either way.")
    if insufficient:
        caveats.append("Too few files to bound ownership reliably.")

    return {
        "confidence": band,
        "regime": regime,
        "value": round(value, 3),
        "probability": round(probability, 3) if probability is not None else None,
        "reliability_band": rel_band,
        "boundary_case": boundary,
        "gated": gated,
        "caveats": caveats,
    }


def format_ownership(interval: dict | None, fallback_pct: float | None) -> str:
    """Render ownership as an interval, never as false-precision. e.g. '~67% (40–86%)'."""
    if interval and not interval.get("insufficient"):
        return f"~{round(interval['point'])}% ({round(interval['lo'])}–{round(interval['hi'])}%)"
    if fallback_pct is not None:
        return f"~{round(fallback_pct)}% (uncertain)"
    return "an unknown share"
