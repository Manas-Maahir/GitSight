"""
Labelled real-repository corpus evaluation.

Where ``scenarios.py`` proves the detectors on *synthetic* repos, this module
evaluates them against *real* repositories carrying **human-assigned** ground-truth
labels (roles and integrity flags) supplied in a JSON manifest.

No labelled data ships with the project: real ground truth must come from a human
annotator (see ``corpus/README.md``). This module provides the schema, loader,
validation, and evaluation so a curated corpus can be plugged in and scored.

The framework is fully unit-tested with an injectable ``predict`` function; the
default predictor clones and analyses each repo via the real pipeline.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eval.metrics import flag_metrics, role_metrics  # noqa: E402

VALID_ROLES = {"Major Contributor", "Minor Contributor", "Free Rider"}
VALID_FLAGS = {"deadline_spike", "bulk_paste", "authorship_laundering", "co_authored_commits"}


@dataclass
class CorpusEntry:
    repo_url: str
    name: str
    roles: dict[str, str] = field(default_factory=dict)
    flags: dict[str, set[str]] = field(default_factory=dict)
    deadline: float | None = None
    notes: str = ""


def validate_entry(raw: dict) -> list[str]:
    """Return a list of human-readable validation errors for one manifest entry."""
    errors: list[str] = []
    if not raw.get("repo_url"):
        errors.append("missing 'repo_url'")
    if not isinstance(raw.get("roles", {}), dict):
        errors.append("'roles' must be an object")
    for author, role in (raw.get("roles") or {}).items():
        if role not in VALID_ROLES:
            errors.append(f"invalid role {role!r} for {author!r}")
    for author, flags in (raw.get("flags") or {}).items():
        if not isinstance(flags, list):
            errors.append(f"'flags' for {author!r} must be a list")
            continue
        for f in flags:
            if f not in VALID_FLAGS:
                errors.append(f"invalid flag {f!r} for {author!r}")
    return errors


def parse_entry(raw: dict) -> CorpusEntry:
    return CorpusEntry(
        repo_url=raw["repo_url"],
        name=raw.get("name", raw["repo_url"]),
        roles=dict(raw.get("roles", {})),
        flags={a: set(v) for a, v in (raw.get("flags") or {}).items()},
        deadline=raw.get("deadline"),
        notes=raw.get("notes", ""),
    )


def load_manifest(path: str) -> list[CorpusEntry]:
    """Load and validate a corpus manifest. Raises ValueError on any invalid entry."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    raw_entries = data["repositories"] if isinstance(data, dict) else data

    all_errors: dict[str, list[str]] = {}
    entries: list[CorpusEntry] = []
    for raw in raw_entries:
        errs = validate_entry(raw)
        label = raw.get("name") or raw.get("repo_url") or "<unnamed>"
        if errs:
            all_errors[label] = errs
        else:
            entries.append(parse_entry(raw))
    if all_errors:
        raise ValueError(f"invalid corpus manifest: {all_errors}")
    return entries


def _default_predict(entry: CorpusEntry) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Clone + analyse a real repo and return predicted roles and flags."""
    from analyzer import analyze_repository
    from scoring import calculate_scores

    data = analyze_repository(entry.repo_url, deadline=entry.deadline)
    authors = calculate_scores(data["stats"])
    roles = {a["author"]: a["role"] for a in authors}
    flags = {a["author"]: {f["type"] for f in a.get("integrity_flags", [])} for a in authors}
    return roles, flags


def evaluate_corpus(entries: list[CorpusEntry], predict=_default_predict) -> dict:
    """Run each labelled repo through *predict* and score it against its labels."""
    per_repo: dict[str, dict] = {}
    roles_pred_all: dict[str, str] = {}
    roles_exp_all: dict[str, str] = {}
    flags_pred_all: dict[str, set[str]] = {}
    flags_exp_all: dict[str, set[str]] = {}

    for entry in entries:
        roles_pred, flags_pred = predict(entry)
        per_repo[entry.name] = {
            "roles": role_metrics(roles_pred, entry.roles),
            "flags": flag_metrics(flags_pred, entry.flags),
        }
        for author in entry.roles:
            roles_pred_all[f"{entry.name}/{author}"] = roles_pred.get(author)
            roles_exp_all[f"{entry.name}/{author}"] = entry.roles[author]
        for author in set(flags_pred) | set(entry.flags):
            flags_pred_all[f"{entry.name}/{author}"] = flags_pred.get(author, set())
            flags_exp_all[f"{entry.name}/{author}"] = entry.flags.get(author, set())

    return {
        "repositories": per_repo,
        "overall": {
            "roles": role_metrics(roles_pred_all, roles_exp_all),
            "flags": flag_metrics(flags_pred_all, flags_exp_all),
        },
    }


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m eval.corpus <manifest.json>")
        raise SystemExit(2)
    entries = load_manifest(argv[0])
    report = evaluate_corpus(entries)
    print(json.dumps(report, indent=2))
    overall = report["overall"]
    print(
        f"\n[{len(entries)} repo(s)] ROLE accuracy: {overall['roles']['accuracy']}  |  "
        f"FLAG precision: {overall['flags']['precision']}  "
        f"recall: {overall['flags']['recall']}  f1: {overall['flags']['f1']}"
    )


if __name__ == "__main__":
    main()
