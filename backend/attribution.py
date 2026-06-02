"""
Line-level contribution attribution.

This module is the foundation of GitSight's integrity instrument. It replaces
naive churn-counting with two complementary, harder-to-game measures:

* **Ownership** — who authored the lines that *survive* in the working tree at
  HEAD, via ``git blame``. Whitespace/reformatting (``-w``) and moves/copies
  (``-M -C``) are ignored so a reformatter or file-mover cannot steal credit.
* **Effort** — how many lines each author *added/removed over history*, from the
  parsed diff of every commit. This captures real work that was later overwritten
  (legitimate) and is the raw substrate for the integrity-forensics layer.

The divergence between the two is itself a signal: high effort with low surviving
ownership means churn/noise or work that teammates replaced.

All identities are keyed by lowercased email; display name is cosmetic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import git

import config

logger = logging.getLogger(__name__)

_AUTHOR_MAIL_RE = re.compile(r"^author-mail <(.*)>$")
_BLAME_HEADER_RE = re.compile(r"^[0-9a-f]{40} \d+ (\d+)")


def is_vendored(path: str) -> bool:
    """True if *path* is vendored, generated, or build output (excluded from scoring)."""
    lowered = path.replace("\\", "/").lower()
    basename = lowered.rsplit("/", 1)[-1]
    if basename in config.GENERATED_BASENAMES:
        return True
    return any(frag in lowered for frag in config.VENDORED_PATH_FRAGMENTS)


def list_source_files(repo_dir: str) -> list[str]:
    """Return git-tracked source files at HEAD, excluding vendored/generated paths."""
    repo = git.Repo(repo_dir)
    try:
        tracked = repo.git.ls_files().splitlines()
    except git.GitCommandError as exc:  # pragma: no cover - defensive
        logger.warning("ls-files failed in %s: %s", repo_dir, exc)
        return []
    return [
        f for f in tracked
        if f.endswith(config.OWNERSHIP_EXTENSIONS) and not is_vendored(f)
    ]


@dataclass
class OwnershipRecord:
    owned_lines: int = 0
    files: set[str] = field(default_factory=set)

    def as_dict(self) -> dict:
        return {"owned_lines": self.owned_lines, "owned_files": len(self.files)}


def _parse_blame_porcelain(text: str) -> dict[int, str]:
    """Parse ``git blame --line-porcelain`` output into {final_line_number: email}."""
    line_map: dict[int, str] = {}
    final_no: int | None = None
    for line in text.splitlines():
        header = _BLAME_HEADER_RE.match(line)
        if header:
            final_no = int(header.group(1))
            continue
        mail = _AUTHOR_MAIL_RE.match(line)
        if mail and final_no is not None:
            line_map[final_no] = mail.group(1).strip().lower()
            final_no = None
    return line_map


def blame_file(repo: git.Repo, path: str) -> dict[int, str]:
    """Return {line_number: author_email} for one file at HEAD."""
    out = repo.git.blame("--line-porcelain", "-w", "-M", "-C", "HEAD", "--", path)
    return _parse_blame_porcelain(out)


def build_line_ownership(
    repo_dir: str, source_files: list[str] | None = None
) -> dict[str, dict[int, str]]:
    """
    Map each source file to its {line_number: author_email} ownership at HEAD.

    This is the shared substrate for both aggregate ownership and function-level
    quality attribution, so the (expensive) blame pass runs only once.
    """
    repo = git.Repo(repo_dir)
    if source_files is None:
        source_files = list_source_files(repo_dir)

    result: dict[str, dict[int, str]] = {}
    for path in source_files:
        try:
            result[path] = blame_file(repo, path)
        except git.GitCommandError:
            continue
    return result


def ownership_from_line_map(line_ownership: dict[str, dict[int, str]]) -> dict[str, OwnershipRecord]:
    """Aggregate a per-file line→author map into per-author ownership totals."""
    ownership: dict[str, OwnershipRecord] = {}
    for path, lines in line_ownership.items():
        for email in lines.values():
            rec = ownership.setdefault(email, OwnershipRecord())
            rec.owned_lines += 1
            rec.files.add(path)
    return ownership


def build_ownership(repo_dir: str, source_files: list[str] | None = None) -> dict[str, OwnershipRecord]:
    """
    Map each author email to the count of lines they own at HEAD.

    Uses ``git blame --line-porcelain -w -M -C`` per file. Failures on individual
    files (binary, unmergeable, deleted) are skipped, not fatal.
    """
    return ownership_from_line_map(build_line_ownership(repo_dir, source_files))


@dataclass
class EffortEvent:
    """One (commit, file) authorship event — the substrate for integrity forensics."""

    commit_sha: str
    author_email: str
    committer_email: str
    timestamp_utc: float  # epoch seconds, tz-aware source
    file: str
    added: int
    deleted: int


def effort_event_from_modified_file(commit, modified_file) -> EffortEvent | None:
    """Build an EffortEvent from a PyDriller commit + modified file, or None if skipped."""
    path = modified_file.new_path or modified_file.old_path or modified_file.filename
    if not path or is_vendored(path):
        return None

    diff = modified_file.diff_parsed or {}
    added = len(diff.get("added", []))
    deleted = len(diff.get("deleted", []))

    return EffortEvent(
        commit_sha=commit.hash,
        author_email=(commit.author.email or "").lower(),
        committer_email=(commit.committer.email or "").lower(),
        timestamp_utc=commit.author_date.timestamp(),
        file=path,
        added=added,
        deleted=deleted,
    )


def aggregate_effort(events: list[EffortEvent]) -> dict[str, dict]:
    """Sum effort events per author email."""
    agg: dict[str, dict] = {}
    for ev in events:
        rec = agg.setdefault(ev.author_email, {"added": 0, "deleted": 0, "commits": set()})
        rec["added"] += ev.added
        rec["deleted"] += ev.deleted
        rec["commits"].add(ev.commit_sha)
    for rec in agg.values():
        rec["commits"] = len(rec["commits"])
    return agg


def combine(
    ownership: dict[str, OwnershipRecord],
    effort: dict[str, dict],
) -> dict[str, dict]:
    """
    Merge ownership and effort into a per-email profile with normalised percentages.

    Returns a mapping email -> {
        owned_lines, owned_files, effort_added, effort_deleted, effort_commits,
        ownership_pct, effort_pct, divergence
    }
    ``divergence`` = effort_pct - ownership_pct (positive = churn that did not survive).
    """
    emails = set(ownership) | set(effort)
    total_owned = sum(r.owned_lines for r in ownership.values()) or 1
    total_effort = sum(e["added"] + e["deleted"] for e in effort.values()) or 1

    profile: dict[str, dict] = {}
    for email in emails:
        own = ownership.get(email, OwnershipRecord())
        eff = effort.get(email, {"added": 0, "deleted": 0, "commits": 0})
        effort_lines = eff["added"] + eff["deleted"]
        ownership_pct = round(own.owned_lines / total_owned * 100, 2)
        effort_pct = round(effort_lines / total_effort * 100, 2)
        profile[email] = {
            "owned_lines": own.owned_lines,
            "owned_files": len(own.files),
            "effort_added": eff["added"],
            "effort_deleted": eff["deleted"],
            "effort_commits": eff["commits"],
            "ownership_pct": ownership_pct,
            "effort_pct": effort_pct,
            "divergence": round(effort_pct - ownership_pct, 2),
        }
    return profile
