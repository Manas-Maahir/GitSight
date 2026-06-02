"""Evaluation metrics: role accuracy and integrity-flag precision/recall/F1."""

from __future__ import annotations


def role_metrics(predicted: dict[str, str], expected: dict[str, str]) -> dict:
    """Accuracy of predicted roles over the expected authors."""
    keys = list(expected.keys())
    correct = sum(1 for k in keys if predicted.get(k) == expected[k])
    return {
        "total": len(keys),
        "correct": correct,
        "accuracy": round(correct / len(keys), 3) if keys else None,
        "errors": [
            {"author": k, "expected": expected[k], "predicted": predicted.get(k)}
            for k in keys if predicted.get(k) != expected[k]
        ],
    }


def flag_metrics(
    predicted: dict[str, set[str]], expected: dict[str, set[str]]
) -> dict:
    """Precision/recall/F1 over (author, flag_type) pairs."""
    tp = fp = fn = 0
    for author in set(predicted) | set(expected):
        p = predicted.get(author, set())
        e = expected.get(author, set())
        tp += len(p & e)
        fp += len(p - e)
        fn += len(e - p)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall else (0.0 if (precision is not None and recall is not None) else None)
    )
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 3) if precision is not None else None,
        "recall": round(recall, 3) if recall is not None else None,
        "f1": round(f1, 3) if f1 is not None else None,
    }
