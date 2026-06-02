"""
Synthetic repositories with injected, known-ground-truth behaviour.

Each builder constructs a throwaway git repo exercising a specific pattern (a free
rider, a deadline dump, a bulk paste, authorship laundering) and returns the repo
path alongside the *expected* roles and integrity flags. The runner then checks
what GitSight actually predicts against this ground truth.

Determinism: commit timestamps are fixed (no wall-clock dependence), so a run is
reproducible. Sizes are chosen with clear separation to avoid borderline verdicts.

NOTE: ``analyze_repository`` deletes the repo it processes (clone cleanup), so each
scenario is built fresh and consumed once.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import git
from git import Actor

_BASE = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

ALICE = Actor("Alice", "alice@example.com")
BOB = Actor("Bob", "bob@example.com")
CAROL = Actor("Carol", "carol@example.com")


@dataclass
class GroundTruth:
    name: str
    roles: dict[str, str]                       # author -> expected role
    flags: dict[str, set[str]] = field(default_factory=dict)  # author -> expected flag types


def _date(day: float) -> str:
    # Format GitPython's parse_date accepts: "YYYY-MM-DD HH:MM:SS +0000".
    return (_BASE + timedelta(days=day)).strftime("%Y-%m-%d %H:%M:%S +0000")


def _new_repo() -> git.Repo:
    return git.Repo.init(tempfile.mkdtemp())


def _finish(repo: git.Repo, gt: GroundTruth) -> tuple[str, GroundTruth]:
    """Release GitPython's file handles so the analyzer can clean up the clone."""
    path = repo.working_tree_dir
    repo.close()
    return path, gt


def _commit(repo, day, author, files: dict[str, str], msg, committer=None):
    for path, content in files.items():
        full = os.path.join(repo.working_tree_dir, path)
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        repo.index.add([path])
    ds = _date(day)
    repo.index.commit(msg, author=author, committer=committer or author,
                      author_date=ds, commit_date=ds)


def _lines(prefix: str, n: int) -> str:
    return "".join(f"{prefix}_{i} = {i}\n" for i in range(n))


# ── Scenarios ────────────────────────────────────────────────────────────────

def balanced_team() -> tuple[str, GroundTruth]:
    """Three contributors of roughly equal weight — all Minor, no flags."""
    repo = _new_repo()
    for day in range(3):
        _commit(repo, day, ALICE, {"a.py": _lines("a", 10 * (day + 1))}, f"alice {day}")
        _commit(repo, day, BOB, {"b.py": _lines("b", 10 * (day + 1))}, f"bob {day}")
        _commit(repo, day, CAROL, {"c.py": _lines("c", 10 * (day + 1))}, f"carol {day}")
    gt = GroundTruth(
        "balanced_team",
        roles={"Alice": "Minor Contributor", "Bob": "Minor Contributor", "Carol": "Minor Contributor"},
    )
    return _finish(repo, gt)


def free_rider() -> tuple[str, GroundTruth]:
    """One dominant author and one barely-contributing free rider."""
    repo = _new_repo()
    for day in range(4):
        _commit(repo, day, ALICE, {
            f"core{day}.py": _lines(f"c{day}", 40),
        }, f"alice {day}")
    _commit(repo, 1, BOB, {"tiny.py": _lines("t", 2)}, "bob tiny")
    gt = GroundTruth(
        "free_rider",
        roles={"Alice": "Major Contributor", "Bob": "Free Rider"},
    )
    return _finish(repo, gt)


def deadline_dumper() -> tuple[str, GroundTruth]:
    """Bob commits all his work in the final slice of the timeline → deadline_spike."""
    repo = _new_repo()
    for day in range(7):
        _commit(repo, day, ALICE, {"a.py": _lines("a", 10 * (day + 1))}, f"alice {day}")
    # Bob: six late commits, each modest (no single bulk-paste outlier).
    for i in range(6):
        _commit(repo, 9 + i * 0.1, BOB, {"b.py": _lines("b", 12 * (i + 1))}, f"bob late {i}")
    gt = GroundTruth(
        "deadline_dumper",
        roles={"Alice": "Minor Contributor", "Bob": "Minor Contributor"},
        flags={"Bob": {"deadline_spike"}},
    )
    return _finish(repo, gt)


def bulk_paster() -> tuple[str, GroundTruth]:
    """Bob drops one massive paste mid-timeline → bulk_paste (no deadline concentration)."""
    repo = _new_repo()
    _commit(repo, 0, ALICE, {"a.py": _lines("a", 150)}, "alice base")
    for i in range(5):
        _commit(repo, i, BOB, {"b.py": _lines("b", 5 * (i + 1))}, f"bob tiny {i}")
    _commit(repo, 4, BOB, {"paste.py": _lines("p", 600)}, "bob paste")
    _commit(repo, 8, ALICE, {"a.py": _lines("a", 160)}, "alice later")  # extend timeline
    gt = GroundTruth(
        "bulk_paster",
        roles={"Alice": "Minor Contributor", "Bob": "Major Contributor"},
        flags={"Bob": {"bulk_paste"}},
    )
    return _finish(repo, gt)


def laundering() -> tuple[str, GroundTruth]:
    """Carol authors her own file but also commits Alice's and Bob's work."""
    repo = _new_repo()
    # Carol commits others' authored work (4 foreign commits).
    _commit(repo, 0, ALICE, {"a.py": _lines("a", 15)}, "a1", committer=CAROL)
    _commit(repo, 1, ALICE, {"a.py": _lines("a", 30)}, "a2", committer=CAROL)
    _commit(repo, 2, BOB, {"b.py": _lines("b", 15)}, "b1", committer=CAROL)
    _commit(repo, 3, BOB, {"b.py": _lines("b", 30)}, "b2", committer=CAROL)
    # Carol's own authored work (so she appears as a contributor).
    _commit(repo, 1, CAROL, {"c.py": _lines("c", 15)}, "c1")
    _commit(repo, 2, CAROL, {"c.py": _lines("c", 30)}, "c2")
    gt = GroundTruth(
        "laundering",
        roles={"Alice": "Minor Contributor", "Bob": "Minor Contributor", "Carol": "Minor Contributor"},
        flags={"Carol": {"authorship_laundering"}},
    )
    return _finish(repo, gt)


DEFAULT_SCENARIOS = {
    "balanced_team": balanced_team,
    "free_rider": free_rider,
    "deadline_dumper": deadline_dumper,
    "bulk_paster": bulk_paster,
    "laundering": laundering,
}


# ── Corrupted-history scenarios (for reliability detection) ───────────────────

@dataclass
class ReliabilityTruth:
    name: str
    expect_band: str          # worst acceptable band, e.g. "low" / "unreliable"
    expect_signal: str        # a reliability factor that must be present


def squashed_history() -> tuple[str, ReliabilityTruth]:
    """Every commit looks like a GitHub squash merge."""
    repo = _new_repo()
    for i in range(8):
        _commit(repo, i, ALICE, {f"f{i}.py": _lines(f"x{i}", 20)}, f"Add feature {i} (#{i + 1})")
    return _finish(repo, ReliabilityTruth("squashed_history", "low", "squash_merges"))


def rebased_history() -> tuple[str, ReliabilityTruth]:
    """Commits whose committer dates are far after their author dates (rebase)."""
    repo = _new_repo()
    for i in range(8):
        path = f"f{i}.py"
        full = os.path.join(repo.working_tree_dir, path)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(_lines(f"x{i}", 15))
        repo.index.add([path])
        author_ds = _date(i)                 # original author time
        committer_ds = _date(100 + i)        # rebased much later
        repo.index.commit(f"commit {i}", author=ALICE, committer=ALICE,
                          author_date=author_ds, commit_date=committer_ds)
    return _finish(repo, ReliabilityTruth("rebased_history", "moderate", "rebase_or_amend"))


def format_bomb_history() -> tuple[str, ReliabilityTruth]:
    """A reformat commit that rewrites many files at once."""
    repo = _new_repo()
    for i in range(25):
        _commit(repo, 0, ALICE, {f"f{i}.py": _lines(f"x{i}", 30)}, f"add f{i}")
    # One commit reformats all 25 files (add≈delete, large churn, many files).
    reformatted = {f"f{i}.py": _lines(f"y{i}", 30) for i in range(25)}
    _commit(repo, 1, BOB, reformatted, "reformat everything")
    return _finish(repo, ReliabilityTruth("format_bomb_history", "moderate", "mass_formatting"))


def thin_history() -> tuple[str, ReliabilityTruth]:
    """Only two commits — too coarse to localise ownership."""
    repo = _new_repo()
    _commit(repo, 0, ALICE, {"a.py": _lines("a", 50)}, "everything")
    _commit(repo, 1, BOB, {"b.py": _lines("b", 50)}, "everything else")
    return _finish(repo, ReliabilityTruth("thin_history", "low", "low_granularity"))


CORRUPTED_SCENARIOS = {
    "squashed_history": squashed_history,
    "rebased_history": rebased_history,
    "format_bomb_history": format_bomb_history,
    "thin_history": thin_history,
}
