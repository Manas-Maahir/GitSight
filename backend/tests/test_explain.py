import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from explain import annotate, build_explanation


def _interval(point=70.0, lo=64.0, hi=76.0, insufficient=False):
    return {"point": point, "lo": lo, "hi": hi, "ci_width": round(hi - lo, 1),
            "n_files": 10, "insufficient": insufficient}


def _record(**overrides):
    base = {
        "author": "Alice",
        "role": "Major Contributor",
        "score": 80.0,
        "ownership_pct": 70.0,
        "ownership_interval": _interval(),
        "boundary_case": False,
        "effort_pct": 65.0,
        "divergence": -5.0,
        "quality": {"assessed": True, "quality_score": 82.0, "avg_cc": 3.0, "complex_functions": 0},
        "integrity_flags": [],
        "stats": {"commits": 50, "attribution": {"owned_files": 12}},
    }
    base.update(overrides)
    return base


class TestBuildExplanation:
    def test_major_headline(self):
        exp = build_explanation(_record())
        assert exp["verdict"] == "Major Contributor"
        assert "Major Contributor" in exp["headline"]

    def test_confidence_never_high_in_cold_start(self):
        # Even a strong, clean case caps at "moderate" without calibration.
        exp = build_explanation(_record())
        assert exp["confidence"] == "moderate"
        assert exp["regime"] == "cold-start"

    def test_ownership_rendered_as_interval_not_false_precision(self):
        exp = build_explanation(_record())
        # No bare 2-decimal percentage; an interval instead.
        assert "70.00%" not in exp["headline"]
        assert "(64–76%)" in exp["headline"] or "~70%" in exp["headline"]

    def test_ownership_is_primary_factor(self):
        exp = build_explanation(_record())
        assert exp["factors"][0]["label"] == "Code ownership"

    def test_free_rider_headline(self):
        exp = build_explanation(_record(role="Free Rider", ownership_pct=2.0,
                                        ownership_interval=_interval(point=2, lo=0, hi=6)))
        assert "Free Rider" in exp["headline"]
        assert exp["factors"][0]["direction"] == "negative"

    def test_no_ownership_is_insufficient(self):
        exp = build_explanation(_record(ownership_pct=None, ownership_interval=None))
        assert exp["confidence"] == "insufficient"
        assert any("manual review" in c for c in exp["caveats"])

    def test_insufficient_interval_caveat(self):
        exp = build_explanation(_record(ownership_interval=_interval(insufficient=True)))
        assert exp["confidence"] == "insufficient"
        assert any("Too few files" in c for c in exp["caveats"])

    def test_boundary_case_caveat(self):
        exp = build_explanation(_record(boundary_case=True))
        assert exp["trust"]["boundary_case"] is True
        assert any("role threshold" in c for c in exp["caveats"])

    def test_low_reliability_gates_confidence(self):
        rel = {"score": 0.15, "band": "unreliable",
               "factors": [{"signal": "squash_merges"}]}
        exp = build_explanation(_record(), reliability=rel)
        assert exp["confidence"] in ("insufficient", "low")
        assert exp["trust"]["gated"] is True
        assert any("unreliable" in c for c in exp["caveats"])

    def test_high_divergence_adds_negative_factor(self):
        exp = build_explanation(_record(divergence=40.0))
        assert "Churn did not survive" in [f["label"] for f in exp["factors"]]

    def test_not_assessed_quality_adds_caveat(self):
        exp = build_explanation(_record(quality={"assessed": False, "quality_score": None}))
        assert any("not assessed" in c for c in exp["caveats"])

    def test_integrity_flag_becomes_factor_with_evidence(self):
        flag = {"type": "bulk_paste", "severity": "high", "detail": "one commit adds 600 lines",
                "evidence": [{"commit": "abc1234", "detail": "600 additions"}]}
        exp = build_explanation(_record(integrity_flags=[flag]))
        flag_factors = [f for f in exp["factors"] if f.get("direction") == "flag"]
        assert flag_factors and flag_factors[0]["label"] == "Bulk paste"
        assert exp["evidence"][0]["commit"] == "abc1234"
        assert "bulk paste" in exp["summary"].lower()

    def test_always_includes_attribution_caveat(self):
        exp = build_explanation(_record())
        assert any("surviving lines at HEAD" in c for c in exp["caveats"])


class TestAnnotate:
    def test_attaches_explanation_in_place(self):
        records = [_record()]
        annotate(records)
        assert "explanation" in records[0]
        assert records[0]["explanation"]["verdict"] == "Major Contributor"

    def test_threads_reliability(self):
        records = [_record()]
        annotate(records, reliability={"score": 0.1, "band": "unreliable", "factors": []})
        assert records[0]["explanation"]["trust"]["gated"] is True
