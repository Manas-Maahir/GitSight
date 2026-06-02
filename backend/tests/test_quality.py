import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import git
import pytest
from git import Actor

import attribution
import quality
from quality import (
    _dominant_owner,
    empty_acc,
    finalize_quality,
    merge_acc,
)

ALICE = Actor("Alice", "alice@example.com")
BOB = Actor("Bob", "bob@example.com")


def _commit_file(repo, rel_path, content, actor, msg):
    full = os.path.join(repo.working_tree_dir, rel_path)
    if os.path.dirname(rel_path):
        os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    repo.index.add([rel_path])
    repo.index.commit(msg, author=actor, committer=actor)


@pytest.fixture()
def repo(tmp_path):
    return git.Repo.init(tmp_path)


class TestDominantOwner:
    def test_picks_majority_owner(self):
        lines = {1: "a@x", 2: "a@x", 3: "b@x"}
        assert _dominant_owner(lines, 1, 3) == "a@x"

    def test_none_when_no_lines_in_range(self):
        assert _dominant_owner({1: "a@x"}, 5, 9) is None


class TestFinalizeQuality:
    def test_not_assessed_for_empty(self):
        result = finalize_quality(empty_acc())
        assert result["assessed"] is False
        assert result["quality_score"] is None

    def test_cc_only(self):
        acc = empty_acc()
        acc["functions"] = 2
        acc["cc_sum"] = 2.0  # avg cc 1.0 -> perfect
        result = finalize_quality(acc)
        assert result["assessed"] is True
        assert result["quality_score"] == 100.0
        assert result["maintainability"] is None

    def test_mi_only(self):
        acc = empty_acc()
        acc["mi_weighted"] = 80.0 * 10
        acc["mi_lines"] = 10
        result = finalize_quality(acc)
        assert result["assessed"] is True
        assert result["maintainability"] == 80.0

    def test_complex_function_lowers_score(self):
        simple = empty_acc()
        simple["functions"], simple["cc_sum"] = 1, 1.0
        complex_ = empty_acc()
        complex_["functions"], complex_["cc_sum"] = 1, 10.0
        assert finalize_quality(simple)["quality_score"] > finalize_quality(complex_)["quality_score"]


class TestMergeAcc:
    def test_merges_in_place(self):
        a = empty_acc()
        a["functions"], a["cc_sum"] = 2, 4.0
        b = empty_acc()
        b["functions"], b["cc_sum"] = 3, 6.0
        merge_acc(a, b)
        assert a["functions"] == 5
        assert a["cc_sum"] == 10.0


class TestAttributeQualityIntegration:
    def test_quality_attributed_to_function_author(self, repo):
        complex_fn = (
            "def classify(n):\n"
            "    if n < 0:\n"
            "        return 'neg'\n"
            "    elif n == 0:\n"
            "        return 'zero'\n"
            "    elif n < 10:\n"
            "        return 'small'\n"
            "    else:\n"
            "        return 'big'\n"
        )
        simple_fn = "def add(a, b):\n    return a + b\n"
        _commit_file(repo, "calc.py", complex_fn, ALICE, "alice complex")
        _commit_file(repo, "simple.py", simple_fn, BOB, "bob simple")

        line_ownership = attribution.build_line_ownership(repo.working_tree_dir)
        accs = quality.attribute_quality(repo.working_tree_dir, line_ownership)

        alice = finalize_quality(accs["alice@example.com"])
        bob = finalize_quality(accs["bob@example.com"])

        assert alice["functions"] == 1
        assert bob["functions"] == 1
        # Alice's branchy function has higher complexity → lower quality score.
        assert alice["avg_cc"] > bob["avg_cc"]
        assert alice["quality_score"] < bob["quality_score"]
