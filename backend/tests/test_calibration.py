import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trust import report
from trust.calibration import (
    Calibrator,
    _fit_isotonic,
    brier,
    ece,
    evaluate,
    reliability_diagram,
    train_from_reviews,
)


class TestPlatt:
    def test_monotone_increasing(self):
        xs = [i / 100 for i in range(100)]
        ys = [1 if x > 0.5 else 0 for x in xs]
        cal = Calibrator()
        cal.fit(xs, ys)
        assert cal.model["method"] == "platt"
        assert cal.predict(0.9) > cal.predict(0.1)

    def test_predict_in_unit_range(self):
        cal = Calibrator()
        cal.fit([0.1, 0.9] * 10, [0, 1] * 10)
        for x in (0.0, 0.5, 1.0):
            p = cal.predict(x)
            assert 0.0 <= p <= 1.0


class TestIsotonic:
    def test_monotone_nondecreasing(self):
        xs = [i / 200 for i in range(200)]
        ys = [1 if x > 0.5 else 0 for x in xs]
        model = _fit_isotonic(xs, ys)
        ps = model["p"]
        assert all(ps[i] <= ps[i + 1] + 1e-9 for i in range(len(ps) - 1))

    def test_calibrator_uses_isotonic_at_scale(self):
        xs = [i / 200 for i in range(200)]
        ys = [1 if x > 0.5 else 0 for x in xs]
        cal = Calibrator()
        cal.fit(xs, ys)
        assert cal.model["method"] == "isotonic"


class TestMetrics:
    def test_ece_zero_for_calibrated(self):
        # Predictions of 0.5 where exactly half are positive → perfectly calibrated.
        preds = [0.5] * 100
        ys = [1, 0] * 50
        assert ece(preds, ys, bins=10) < 1e-9

    def test_ece_high_for_miscalibrated(self):
        preds = [0.9] * 100
        ys = [0] * 100
        assert ece(preds, ys, bins=10) > 0.8

    def test_brier(self):
        assert brier([1.0, 0.0], [1, 0]) == 0.0
        assert brier([0.0, 1.0], [1, 0]) == 1.0

    def test_reliability_diagram_bins(self):
        diagram = reliability_diagram([0.05, 0.95], [0, 1], bins=10)
        assert len(diagram) == 10
        assert sum(b["count"] for b in diagram) == 2


class TestTrainFromReviews:
    def _reviews(self, n):
        out = []
        for i in range(n):
            x = (i % 10) / 10
            out.append({"confidence_value": x, "agreed": 1 if x > 0.5 else 0})
        return out

    def test_insufficient_labels_stays_cold_start(self):
        cal, status = train_from_reviews(self._reviews(10))
        assert cal is None
        assert status["regime"] == "cold-start"

    def test_single_class_cannot_calibrate(self):
        reviews = [{"confidence_value": 0.5, "agreed": 1} for _ in range(60)]
        cal, status = train_from_reviews(reviews)
        assert cal is None
        assert "one class" in status["reason"]

    def test_sufficient_labels_calibrate(self):
        cal, metrics = train_from_reviews(self._reviews(60))
        assert cal is not None and cal.ready
        assert metrics["regime"] == "calibrated"
        assert "ece" in metrics and "ece_ci" in metrics

    def test_evaluate_shape(self):
        cal = Calibrator()
        cal.fit([0.1, 0.9] * 20, [0, 1] * 20)
        m = evaluate(cal, [0.1, 0.9] * 20, [0, 1] * 20)
        assert set(m) >= {"n", "ece", "ece_ci", "brier", "reliability_diagram"}


class TestCalibratedRegimeInReport:
    def test_ready_calibrator_yields_calibrated_regime(self):
        cal, _ = train_from_reviews(
            [{"confidence_value": (i % 10) / 10, "agreed": 1 if (i % 10) / 10 > 0.5 else 0}
             for i in range(60)]
        )
        record = {
            "ownership_interval": {"point": 70, "lo": 64, "hi": 76, "ci_width": 12, "insufficient": False},
            "boundary_case": False,
        }
        trust = report.build_trust(record, reliability={"score": 1.0, "band": "high"}, calibrator=cal)
        assert trust["regime"] == "calibrated"
        assert trust["probability"] is not None
