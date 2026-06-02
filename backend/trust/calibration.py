"""
Confidence calibration.

Turns GitSight's raw, conservative confidence score into an **empirically calibrated
probability** that a role verdict is correct, learned from instructor reviews
(agreements *and* corrections — the unbiased label source from `store.reviews`).

Two estimators, chosen by label volume:

* **Platt scaling** — a 1-D logistic ``p = σ(a·x + b)``; smooth, stable for small N.
* **Isotonic regression** (Pool-Adjacent-Violators) — monotone, non-parametric; used
  once enough labels exist to avoid overfitting.

Calibration quality is reported with **Expected Calibration Error (ECE)**, the
**Brier score**, and **reliability-diagram** data — each with a bootstrap CI, because
with few labels the metrics are themselves uncertain and must say so.

No third-party ML dependency: both estimators are implemented in the standard library.
"""

from __future__ import annotations

import json
import math
import random

import config


def _sigmoid(z: float) -> float:
    if z < -60:
        return 0.0
    if z > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def _fit_platt(xs: list[float], ys: list[int], iters: int = 2000, lr: float = 0.1) -> dict:
    """Fit p = sigmoid(a*x + b) by gradient descent (stable for small samples)."""
    a, b = 0.0, 0.0
    n = len(xs)
    for _ in range(iters):
        ga = gb = 0.0
        for x, y in zip(xs, ys):
            p = _sigmoid(a * x + b)
            err = p - y
            ga += err * x
            gb += err
        a -= lr * ga / n
        b -= lr * gb / n
    return {"method": "platt", "a": a, "b": b}


def _fit_isotonic(xs: list[float], ys: list[int]) -> dict:
    """Pool-Adjacent-Violators isotonic regression → monotone step function."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    sx = [xs[i] for i in order]
    sy = [float(ys[i]) for i in order]
    # Each block: [sum, weight, value].
    blocks: list[list[float]] = []
    for v in sy:
        blocks.append([v, 1.0, v])
        while len(blocks) > 1 and blocks[-2][2] > blocks[-1][2]:
            s2, w2, _ = blocks.pop()
            s1, w1, _ = blocks.pop()
            s, w = s1 + s2, w1 + w2
            blocks.append([s, w, s / w])
    # Expand block values back to points, then collapse to (x, p) thresholds.
    values: list[float] = []
    for s, w, val in blocks:
        values.extend([val] * int(w))
    points = sorted(set(zip(sx, values)))
    thresholds = [p[0] for p in points]
    probs = [p[1] for p in points]
    return {"method": "isotonic", "x": thresholds, "p": probs}


class Calibrator:
    def __init__(self, model: dict | None = None):
        self.model = model

    @property
    def ready(self) -> bool:
        return self.model is not None

    def fit(self, xs: list[float], ys: list[int]) -> None:
        if len(xs) >= config.TRUST_ISO_MIN_LABELS:
            self.model = _fit_isotonic(xs, ys)
        else:
            self.model = _fit_platt(xs, ys)

    def predict(self, x: float) -> float | None:
        if not self.model:
            return None
        if self.model["method"] == "platt":
            return _sigmoid(self.model["a"] * x + self.model["b"])
        xs, ps = self.model["x"], self.model["p"]
        if x <= xs[0]:
            return ps[0]
        if x >= xs[-1]:
            return ps[-1]
        for i in range(1, len(xs)):
            if x <= xs[i]:
                # linear interpolation between isotonic steps
                t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]) if xs[i] != xs[i - 1] else 0.0
                return ps[i - 1] + t * (ps[i] - ps[i - 1])
        return ps[-1]

    def to_json(self) -> str:
        return json.dumps(self.model)

    @classmethod
    def from_json(cls, s: str) -> Calibrator:
        return cls(json.loads(s))


# ── Metrics ──────────────────────────────────────────────────────────────────

def brier(preds: list[float], ys: list[int]) -> float:
    if not preds:
        return 0.0
    return sum((p - y) ** 2 for p, y in zip(preds, ys)) / len(preds)


def ece(preds: list[float], ys: list[int], bins: int = 10) -> float:
    """Expected Calibration Error: weighted gap between confidence and accuracy."""
    if not preds:
        return 0.0
    n = len(preds)
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(preds) if (lo < p <= hi) or (b == 0 and p == 0.0)]
        if not idx:
            continue
        conf = sum(preds[i] for i in idx) / len(idx)
        acc = sum(ys[i] for i in idx) / len(idx)
        total += abs(conf - acc) * len(idx) / n
    return total


def reliability_diagram(preds: list[float], ys: list[int], bins: int = 10) -> list[dict]:
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(preds) if (lo < p <= hi) or (b == 0 and p == 0.0)]
        if not idx:
            out.append({"bin": [round(lo, 2), round(hi, 2)], "count": 0,
                        "confidence": None, "accuracy": None})
            continue
        out.append({
            "bin": [round(lo, 2), round(hi, 2)],
            "count": len(idx),
            "confidence": round(sum(preds[i] for i in idx) / len(idx), 3),
            "accuracy": round(sum(ys[i] for i in idx) / len(idx), 3),
        })
    return out


def _bootstrap_ci(values: list[float], samples: int = 500, seed: int = 7) -> tuple[float, float]:
    if len(values) < 2:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    n = len(values)
    for _ in range(samples):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return (round(means[int(0.05 * samples)], 3), round(means[int(0.95 * samples)], 3))


def evaluate(calibrator: Calibrator, xs: list[float], ys: list[int], bins: int = 10) -> dict:
    """Compute ECE (with bootstrap CI), Brier, and reliability-diagram data."""
    preds = [calibrator.predict(x) for x in xs]
    preds = [p if p is not None else 0.0 for p in preds]
    # Per-point absolute calibration error → bootstrap an ECE-like CI.
    point_err = [abs(p - y) for p, y in zip(preds, ys)]
    lo, hi = _bootstrap_ci(point_err)
    return {
        "n": len(xs),
        "ece": round(ece(preds, ys, bins), 4),
        "ece_ci": [lo, hi],
        "brier": round(brier(preds, ys), 4),
        "reliability_diagram": reliability_diagram(preds, ys, bins),
    }


# ── Training from reviews ─────────────────────────────────────────────────────

def _labels_from_reviews(reviews: list[dict]) -> tuple[list[float], list[int]]:
    xs, ys = [], []
    for r in reviews:
        cv = r.get("confidence_value")
        if cv is None:
            continue
        xs.append(float(cv))
        ys.append(int(r.get("agreed", 0)))
    return xs, ys


def train_from_reviews(reviews: list[dict]) -> tuple[Calibrator | None, dict]:
    """Fit a calibrator from reviews if enough labels exist; return (calibrator, status)."""
    xs, ys = _labels_from_reviews(reviews)
    n = len(xs)
    if n < config.TRUST_CALIB_MIN_LABELS:
        return None, {"regime": "cold-start", "n_labels": n,
                      "needed": config.TRUST_CALIB_MIN_LABELS,
                      "reason": "insufficient labels for calibration"}
    if len(set(ys)) < 2:
        return None, {"regime": "cold-start", "n_labels": n,
                      "reason": "labels are all one class — cannot calibrate"}
    cal = Calibrator()
    cal.fit(xs, ys)
    metrics = evaluate(cal, xs, ys)
    metrics["regime"] = "calibrated"
    metrics["method"] = cal.model["method"]
    return cal, metrics
