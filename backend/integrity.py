"""
Academic-integrity forensics.

Each detector consumes the attribution effort log (plus commit messages) and
produces evidence-bearing flags keyed by author email. Flags are **advisory and
surfaced separately** — they are never folded into the contribution score, so a
grader sees every signal and can act on (or dismiss) it transparently.

A flag is a dict:
    {
        "type": str,            # e.g. "deadline_spike"
        "severity": str,        # "low" | "medium" | "high" | "advisory"
        "score": float,         # 0-1 strength
        "detail": str,          # human summary
        "evidence": [ {"commit": sha, "detail": str}, ... ],
    }
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass

import config
from attribution import EffortEvent

_CO_AUTHOR_RE = re.compile(r"co-authored-by:.*?<([^>]+)>", re.IGNORECASE)


@dataclass
class CommitAgg:
    sha: str
    author_email: str
    committer_email: str
    timestamp_utc: float
    added: int
    deleted: int


def parse_co_authors(msg: str | None) -> list[str]:
    return [m.strip().lower() for m in _CO_AUTHOR_RE.findall(msg or "")]


def _is_bot(email: str) -> bool:
    return any(frag in email for frag in config.INTEGRITY_BOT_EMAIL_FRAGMENTS)


def aggregate_commits(events: list[EffortEvent]) -> list[CommitAgg]:
    """Collapse per-(commit, file) events into one record per commit."""
    by_sha: dict[str, CommitAgg] = {}
    for ev in events:
        rec = by_sha.get(ev.commit_sha)
        if rec is None:
            rec = CommitAgg(
                sha=ev.commit_sha,
                author_email=ev.author_email,
                committer_email=ev.committer_email,
                timestamp_utc=ev.timestamp_utc,
                added=0,
                deleted=0,
            )
            by_sha[ev.commit_sha] = rec
        rec.added += ev.added
        rec.deleted += ev.deleted
    return list(by_sha.values())


def detect_deadline_spike(
    commits: list[CommitAgg], deadline: float | None = None
) -> dict[str, dict]:
    """Flag authors who concentrate their additions in the final slice of the timeline."""
    if not commits:
        return {}
    times = [c.timestamp_utc for c in commits]
    start, end = min(times), (deadline if deadline is not None else max(times))
    span = end - start
    if span <= 0:
        return {}

    window_start = end - span * config.INTEGRITY_DEADLINE_WINDOW
    total = defaultdict(float)
    late = defaultdict(lambda: {"lines": 0.0, "commits": []})
    for c in commits:
        total[c.author_email] += c.added
        if c.timestamp_utc >= window_start:
            late[c.author_email]["lines"] += c.added
            late[c.author_email]["commits"].append(c.sha)

    flags: dict[str, dict] = {}
    for email, tot in total.items():
        if tot <= 0:
            continue
        late_lines = late[email]["lines"]
        ratio = late_lines / tot
        if (
            ratio >= config.INTEGRITY_DEADLINE_RATIO
            and late_lines >= config.INTEGRITY_DEADLINE_MIN_LINES
        ):
            flags[email] = {
                "type": "deadline_spike",
                "severity": "high" if ratio >= 0.85 else "medium",
                "score": round(ratio, 2),
                "detail": (
                    f"{round(ratio * 100)}% of additions ({int(late_lines)} lines) landed "
                    f"in the final {round(config.INTEGRITY_DEADLINE_WINDOW * 100)}% of the timeline"
                ),
                "evidence": [{"commit": sha, "detail": "late commit"}
                             for sha in late[email]["commits"][:10]],
            }
    return flags


def detect_bulk_paste(commits: list[CommitAgg]) -> dict[str, dict]:
    """Flag commits whose additions are a statistical outlier for that author."""
    by_author: dict[str, list[CommitAgg]] = defaultdict(list)
    for c in commits:
        by_author[c.author_email].append(c)

    flags: dict[str, dict] = {}
    for email, cs in by_author.items():
        if len(cs) < config.INTEGRITY_PASTE_MIN_COMMITS:
            continue
        adds = [c.added for c in cs]
        median = statistics.median(adds)
        # Robust threshold: a commit must clear both an absolute floor and a large
        # multiple of the author's typical commit size to count as anomalous.
        threshold = max(
            float(config.INTEGRITY_PASTE_FLOOR),
            median * config.INTEGRITY_PASTE_MEDIAN_MULT,
        )
        outliers = [
            c for c in cs
            if c.added >= threshold and c.added >= config.INTEGRITY_PASTE_FLOOR
        ]
        if outliers:
            biggest = max(outliers, key=lambda c: c.added)
            flags[email] = {
                "type": "bulk_paste",
                "severity": "high" if biggest.added >= 3 * config.INTEGRITY_PASTE_FLOOR else "medium",
                "score": round(min(1.0, len(outliers) / len(cs) + 0.3), 2),
                "detail": (
                    f"{len(outliers)} commit(s) add far more than this author's norm "
                    f"(largest: {biggest.added} lines vs median {round(median)})"
                ),
                "evidence": [{"commit": c.sha, "detail": f"{c.added} additions"}
                             for c in sorted(outliers, key=lambda c: -c.added)[:10]],
            }
    return flags


def detect_authorship_laundering(commits: list[CommitAgg]) -> dict[str, dict]:
    """Flag a person who commits a notable amount of *another* person's authored work."""
    foreign: dict[str, list[CommitAgg]] = defaultdict(list)
    for c in commits:
        committer = c.committer_email
        author = c.author_email
        if not committer or not author or committer == author:
            continue
        if _is_bot(committer) or _is_bot(author):
            continue
        foreign[committer].append(c)

    flags: dict[str, dict] = {}
    for committer, cs in foreign.items():
        if len(cs) >= config.INTEGRITY_LAUNDERING_MIN:
            authors = {c.author_email for c in cs}
            flags[committer] = {
                "type": "authorship_laundering",
                "severity": "advisory",
                "score": round(min(1.0, len(cs) / 10.0), 2),
                "detail": (
                    f"committed {len(cs)} commit(s) authored by others "
                    f"({len(authors)} distinct author(s)) — verify attribution"
                ),
                "evidence": [{"commit": c.sha, "detail": f"authored by {c.author_email}"}
                             for c in cs[:10]],
            }
    return flags


def analyze(
    events: list[EffortEvent],
    commit_messages: dict[str, str] | None = None,
    deadline: float | None = None,
) -> dict[str, list[dict]]:
    """Run all detectors and return {email: [flag, ...]}."""
    commits = aggregate_commits(events)
    per_email: dict[str, list[dict]] = defaultdict(list)

    for detector_result in (
        detect_deadline_spike(commits, deadline),
        detect_bulk_paste(commits),
        detect_authorship_laundering(commits),
    ):
        for email, flag in detector_result.items():
            per_email[email].append(flag)

    # Co-authored-by trailers — advisory note attached to the commit author.
    if commit_messages:
        co_counts: dict[str, int] = defaultdict(int)
        seen: dict[str, set[str]] = defaultdict(set)
        agg_by_sha = {c.sha: c for c in commits}
        for sha, msg in commit_messages.items():
            co = parse_co_authors(msg)
            commit = agg_by_sha.get(sha)
            if commit and co:
                seen[commit.author_email].update(co)
                co_counts[commit.author_email] += 1
        for author, count in co_counts.items():
            per_email[author].append({
                "type": "co_authored_commits",
                "severity": "advisory",
                "score": round(min(1.0, count / 10.0), 2),
                "detail": f"{count} commit(s) declare co-authors ({len(seen[author])} distinct)",
                "evidence": [],
            })

    return dict(per_email)
