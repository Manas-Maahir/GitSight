import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring import calculate_scores


def _make_stats(**overrides):
    base = {
        "commits": 10,
        "lines_added": 100,
        "lines_deleted": 20,
        "files_modified": 15,
        "files": ["a.py"],
        "avg_quality": 80.0,
    }
    base.update(overrides)
    return base


class TestCalculateScoresEmpty:
    def test_empty_stats_returns_empty_list(self):
        assert calculate_scores({}) == []

    def test_zero_commits_returns_minor_contributors(self):
        stats = {"Alice": _make_stats(commits=0, lines_added=0, lines_deleted=0, files_modified=0)}
        result = calculate_scores(stats)
        assert result[0]["role"] == "Minor Contributor"


class TestRoleAssignment:
    def test_sole_contributor_is_major(self):
        stats = {"Alice": _make_stats()}
        result = calculate_scores(stats)
        assert result[0]["role"] == "Major Contributor"

    def test_dominant_contributor_is_major(self):
        stats = {
            "Alice": _make_stats(commits=90, lines_added=900, lines_deleted=0, files_modified=90),
            "Bob": _make_stats(commits=10, lines_added=100, lines_deleted=0, files_modified=10),
        }
        result = calculate_scores(stats)
        assert result[0]["author"] == "Alice"
        assert result[0]["role"] == "Major Contributor"

    def test_free_rider_detection(self):
        stats = {
            "Alice": _make_stats(commits=99, lines_added=990, lines_deleted=0, files_modified=99),
            "Bob": _make_stats(commits=1, lines_added=1, lines_deleted=0, files_modified=1),
        }
        result = calculate_scores(stats)
        bob = next(a for a in result if a["author"] == "Bob")
        assert bob["role"] == "Free Rider"

    def test_sorted_by_score_descending(self):
        stats = {
            "Alice": _make_stats(commits=50, lines_added=500, lines_deleted=0, files_modified=50),
            "Bob": _make_stats(commits=50, lines_added=500, lines_deleted=0, files_modified=50),
        }
        result = calculate_scores(stats)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)


class TestScoreValues:
    def test_scores_are_rounded_to_two_decimals(self):
        stats = {"Alice": _make_stats()}
        result = calculate_scores(stats)
        score_str = str(result[0]["score"])
        if "." in score_str:
            assert len(score_str.split(".")[1]) <= 2

    def test_quality_score_included(self):
        stats = {"Alice": _make_stats(avg_quality=75.5)}
        result = calculate_scores(stats)
        assert result[0]["quality_score"] == 75.5

    def test_integrity_flags_passthrough(self):
        stats = {"Alice": _make_stats(integrity_flags=[{"type": "spike"}])}
        result = calculate_scores(stats)
        assert result[0]["integrity_flags"] == [{"type": "spike"}]


def _make_attr_stats(ownership_pct, effort_pct, owned_files, avg_quality=80.0):
    return {
        "commits": 1, "lines_added": 1, "lines_deleted": 0, "files_modified": 1,
        "files": ["a.py"], "avg_quality": avg_quality,
        "attribution": {
            "owned_lines": int(ownership_pct),
            "owned_files": owned_files,
            "effort_added": int(effort_pct),
            "effort_deleted": 0,
            "effort_commits": 1,
            "ownership_pct": ownership_pct,
            "effort_pct": effort_pct,
            "divergence": round(effort_pct - ownership_pct, 2),
        },
    }


class TestOwnershipMode:
    def test_ownership_fields_surfaced(self):
        stats = {"Alice": _make_attr_stats(100.0, 100.0, 1)}
        result = calculate_scores(stats)
        assert result[0]["ownership_pct"] == 100.0
        assert result[0]["effort_pct"] == 100.0

    def test_high_ownership_is_major(self):
        stats = {
            "Alice": _make_attr_stats(98.0, 95.0, 10),
            "Bob": _make_attr_stats(2.0, 5.0, 0),
        }
        result = calculate_scores(stats)
        alice = next(a for a in result if a["author"] == "Alice")
        assert alice["role"] == "Major Contributor"

    def test_low_ownership_low_effort_is_free_rider(self):
        stats = {
            "Alice": _make_attr_stats(98.0, 95.0, 10),
            "Bob": _make_attr_stats(2.0, 5.0, 0),
        }
        result = calculate_scores(stats)
        bob = next(a for a in result if a["author"] == "Bob")
        assert bob["role"] == "Free Rider"

    def test_churn_padder_is_discounted(self):
        # Bob churned 60% of all lines but almost none of it survives. Under the
        # old LOC model he would look like a Major contributor; ownership-primary
        # scoring must discount him well below his raw effort share.
        stats = {
            "Alice": _make_attr_stats(90.0, 40.0, 8),
            "Bob": _make_attr_stats(10.0, 60.0, 2),
        }
        result = calculate_scores(stats)
        bob = next(a for a in result if a["author"] == "Bob")
        assert bob["score"] < bob["effort_pct"]  # churn discounted, not rewarded
        assert bob["role"] != "Major Contributor"
        assert result[0]["author"] == "Alice"  # real author ranks first
