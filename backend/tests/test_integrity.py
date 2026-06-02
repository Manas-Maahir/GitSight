import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from attribution import EffortEvent
from integrity import (
    CommitAgg,
    aggregate_commits,
    analyze,
    detect_authorship_laundering,
    detect_bulk_paste,
    detect_deadline_spike,
    parse_co_authors,
)


def _commit(sha, author, added, ts=0.0, committer=None):
    return CommitAgg(
        sha=sha,
        author_email=author,
        committer_email=committer or author,
        timestamp_utc=ts,
        added=added,
        deleted=0,
    )


class TestParseCoAuthors:
    def test_extracts_emails(self):
        msg = "feat: x\n\nCo-authored-by: Bob <bob@example.com>\nCo-Authored-By: Cy <cy@x.io>"
        assert parse_co_authors(msg) == ["bob@example.com", "cy@x.io"]

    def test_empty(self):
        assert parse_co_authors("no trailers here") == []
        assert parse_co_authors(None) == []


class TestAggregateCommits:
    def test_collapses_events_per_commit(self):
        events = [
            EffortEvent("c1", "a@x", "a@x", 1.0, "a.py", 10, 1),
            EffortEvent("c1", "a@x", "a@x", 1.0, "b.py", 5, 0),
            EffortEvent("c2", "b@x", "b@x", 2.0, "c.py", 3, 0),
        ]
        commits = {c.sha: c for c in aggregate_commits(events)}
        assert commits["c1"].added == 15
        assert commits["c2"].added == 3


class TestDeadlineSpike:
    def test_late_dump_flagged(self):
        commits = [
            _commit("early", "bob@x", 100, ts=10.0),
            _commit("late", "alice@x", 100, ts=95.0),
        ]
        flags = detect_deadline_spike(commits)
        assert "alice@x" in flags
        assert flags["alice@x"]["type"] == "deadline_spike"
        assert "bob@x" not in flags

    def test_small_late_contribution_not_flagged(self):
        commits = [
            _commit("early", "bob@x", 1000, ts=10.0),
            _commit("late", "alice@x", 5, ts=95.0),  # below min lines
        ]
        flags = detect_deadline_spike(commits)
        assert "alice@x" not in flags


class TestBulkPaste:
    def test_outlier_commit_flagged(self):
        commits = [_commit(f"s{i}", "alice@x", 5, ts=float(i)) for i in range(10)]
        commits.append(_commit("paste", "alice@x", 600, ts=11.0))
        flags = detect_bulk_paste(commits)
        assert "alice@x" in flags
        assert flags["alice@x"]["type"] == "bulk_paste"
        assert flags["alice@x"]["evidence"][0]["commit"] == "paste"

    def test_consistent_author_not_flagged(self):
        commits = [_commit(f"s{i}", "bob@x", 50, ts=float(i)) for i in range(10)]
        assert "bob@x" not in detect_bulk_paste(commits)

    def test_too_few_commits_skipped(self):
        commits = [_commit("s0", "a@x", 5), _commit("s1", "a@x", 9000)]
        assert detect_bulk_paste(commits) == {}


class TestAuthorshipLaundering:
    def test_committing_others_work_flagged(self):
        commits = [
            _commit(f"c{i}", "alice@x", 10, ts=float(i), committer="carol@x")
            for i in range(3)
        ]
        flags = detect_authorship_laundering(commits)
        assert "carol@x" in flags
        assert flags["carol@x"]["severity"] == "advisory"

    def test_bot_committer_ignored(self):
        commits = [
            _commit(f"c{i}", "alice@x", 10, ts=float(i), committer="noreply@github.com")
            for i in range(5)
        ]
        assert detect_authorship_laundering(commits) == {}

    def test_self_committed_not_flagged(self):
        commits = [_commit(f"c{i}", "alice@x", 10, ts=float(i)) for i in range(5)]
        assert detect_authorship_laundering(commits) == {}


class TestAnalyze:
    def test_returns_flags_keyed_by_email(self):
        events = [EffortEvent("late", "alice@x", "alice@x", 95.0, "a.py", 100, 0),
                  EffortEvent("early", "bob@x", "bob@x", 10.0, "b.py", 100, 0)]
        result = analyze(events)
        assert "alice@x" in result
        assert any(f["type"] == "deadline_spike" for f in result["alice@x"])

    def test_co_authored_trailer_flag(self):
        events = [EffortEvent("c1", "alice@x", "alice@x", 1.0, "a.py", 10, 0)]
        msgs = {"c1": "feat\n\nCo-authored-by: Bob <bob@x>"}
        result = analyze(events, msgs)
        assert any(f["type"] == "co_authored_commits" for f in result["alice@x"])
