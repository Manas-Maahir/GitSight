"""
Run the GitSight pipeline over the synthetic scenarios and score it against the
injected ground truth.

Usage:
    python -m eval.runner            # from the backend/ directory
"""

from __future__ import annotations

import json
import os
import sys

# Allow running both as a module (python -m eval.runner) and directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import analyze_repository  # noqa: E402
from eval import scenarios  # noqa: E402
from eval.metrics import flag_metrics, role_metrics  # noqa: E402
from scoring import calculate_scores  # noqa: E402


def run_scenario(build) -> tuple[dict[str, str], dict[str, set[str]], scenarios.GroundTruth]:
    """Build a scenario, run the full pipeline, return predicted roles + flags + ground truth."""
    repo_dir, gt = build()
    data = analyze_repository(repo_dir)
    authors = calculate_scores(data["stats"])
    predicted_roles = {a["author"]: a["role"] for a in authors}
    predicted_flags = {
        a["author"]: {f["type"] for f in a.get("integrity_flags", [])}
        for a in authors
    }
    return predicted_roles, predicted_flags, gt


def evaluate(builders: dict | None = None) -> dict:
    builders = builders or scenarios.DEFAULT_SCENARIOS
    per_scenario: dict[str, dict] = {}
    all_roles_pred: dict[str, str] = {}
    all_roles_exp: dict[str, str] = {}
    all_flags_pred: dict[str, set[str]] = {}
    all_flags_exp: dict[str, set[str]] = {}

    for name, build in builders.items():
        roles_pred, flags_pred, gt = run_scenario(build)
        per_scenario[name] = {
            "roles": role_metrics(roles_pred, gt.roles),
            "flags": flag_metrics(flags_pred, gt.flags),
        }
        for author in gt.roles:
            all_roles_pred[f"{name}/{author}"] = roles_pred.get(author)
            all_roles_exp[f"{name}/{author}"] = gt.roles[author]
        for author in set(flags_pred) | set(gt.flags):
            all_flags_pred[f"{name}/{author}"] = flags_pred.get(author, set())
            all_flags_exp[f"{name}/{author}"] = gt.flags.get(author, set())

    return {
        "scenarios": per_scenario,
        "overall": {
            "roles": role_metrics(all_roles_pred, all_roles_exp),
            "flags": flag_metrics(all_flags_pred, all_flags_exp),
        },
    }


def main() -> None:
    report = evaluate()
    print(json.dumps(report, indent=2))
    overall = report["overall"]
    print(
        f"\nROLE accuracy: {overall['roles']['accuracy']}  |  "
        f"FLAG precision: {overall['flags']['precision']}  "
        f"recall: {overall['flags']['recall']}  f1: {overall['flags']['f1']}"
    )


if __name__ == "__main__":
    main()
