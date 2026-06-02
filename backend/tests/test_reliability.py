import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import analyze_repository
from eval import scenarios
from trust import reliability


def _commit(sha="c", msg="msg", author_ts=1000.0, committer_ts=1000.0,
            added=10, deleted=5, files=2):
    return {
        "sha": sha, "msg": msg,
        "author_email": "a@x", "committer_email": "a@x",
        "author_ts": author_ts, "committer_ts": committer_ts,
        "added": added, "deleted": deleted, "files": files,
    }


class TestDetectors:
    def test_squash_detected(self):
        commits = [_commit(sha=str(i), msg=f"Add thing {i} (#{i})") for i in range(8)]
        penalty, factor, ev = reliability.detect_squash(commits)
        assert penalty > 0 and factor["signal"] == "squash_merges"
        assert len(ev) > 0

    def test_clean_messages_no_squash(self):
        commits = [_commit(sha=str(i), msg="normal commit message") for i in range(8)]
        assert reliability.detect_squash(commits)[0] == 0.0

    def test_rebase_detected_by_date_gap(self):
        commits = [_commit(sha=str(i), author_ts=1000.0, committer_ts=1000.0 + 10 * 86400)
                   for i in range(8)]
        penalty, factor, _ = reliability.detect_rebase(commits)
        assert penalty > 0 and factor["signal"] == "rebase_or_amend"

    def test_format_bomb_detected(self):
        commits = [_commit(sha="bomb", added=800, deleted=800, files=30)]
        penalty, factor, _ = reliability.detect_format_bombs(commits)
        assert penalty > 0 and factor["signal"] == "mass_formatting"

    def test_normal_commit_not_a_bomb(self):
        assert reliability.detect_format_bombs([_commit(added=10, deleted=5, files=2)])[0] == 0.0

    def test_low_granularity(self):
        penalty, factor, _ = reliability.detect_low_granularity([_commit(), _commit()])
        assert penalty > 0 and factor["signal"] == "low_granularity"

    def test_future_timestamp_anomaly(self):
        future = time.time() + 10 * 86400
        commits = [_commit(sha=str(i), author_ts=future, committer_ts=future) for i in range(4)]
        penalty, factor, _ = reliability.detect_timestamp_anomalies(commits)
        assert penalty > 0 and factor["signal"] == "timestamp_anomalies"


class TestAssess:
    def test_clean_history_high(self):
        commits = [_commit(sha=str(i), msg=f"fix {i}", added=10, deleted=2, files=1)
                   for i in range(30)]
        report = reliability.assess(commits)
        assert report.band == "high"
        assert report.factors == []

    def test_product_collapses_on_squash(self):
        commits = [_commit(sha=str(i), msg=f"feat (#{i})") for i in range(30)]
        report = reliability.assess(commits)
        assert report.score < 0.2
        assert report.band == "unreliable"

    def test_empty(self):
        assert reliability.assess([]).band == "high"


class TestCorruptedScenariosIntegration:
    def _run(self, build):
        repo_dir, truth = build()
        data = analyze_repository(repo_dir)
        return data["reliability"], truth

    def test_squashed(self):
        rel, truth = self._run(scenarios.squashed_history)
        signals = {f["signal"] for f in rel["factors"]}
        assert truth.expect_signal in signals
        assert rel["band"] != "high"

    def test_rebased(self):
        rel, truth = self._run(scenarios.rebased_history)
        signals = {f["signal"] for f in rel["factors"]}
        assert truth.expect_signal in signals

    def test_format_bomb(self):
        rel, truth = self._run(scenarios.format_bomb_history)
        signals = {f["signal"] for f in rel["factors"]}
        assert truth.expect_signal in signals

    def test_thin(self):
        rel, truth = self._run(scenarios.thin_history)
        signals = {f["signal"] for f in rel["factors"]}
        assert truth.expect_signal in signals
        assert rel["band"] != "high"

    def test_clean_synthetic_is_not_flagged(self):
        repo_dir, _gt = scenarios.balanced_team()
        data = analyze_repository(repo_dir)
        # The balanced team has 9 commits (< 10) so low_granularity may fire, but
        # no squash/rebase/format/timestamp signal should.
        signals = {f["signal"] for f in data["reliability"]["factors"]}
        assert "squash_merges" not in signals
        assert "rebase_or_amend" not in signals
        assert "mass_formatting" not in signals
        assert "timestamp_anomalies" not in signals
