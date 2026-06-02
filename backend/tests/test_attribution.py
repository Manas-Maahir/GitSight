import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import git
import pytest
from git import Actor

from attribution import (
    EffortEvent,
    OwnershipRecord,
    aggregate_effort,
    build_ownership,
    combine,
    is_vendored,
    list_source_files,
)

ALICE = Actor("Alice", "alice@example.com")
BOB = Actor("Bob", "bob@example.com")


def _commit_file(repo: git.Repo, rel_path: str, content: str, actor: Actor, msg: str) -> None:
    full = os.path.join(repo.working_tree_dir, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(rel_path) else None
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    repo.index.add([rel_path])
    repo.index.commit(msg, author=actor, committer=actor)


@pytest.fixture()
def repo(tmp_path):
    return git.Repo.init(tmp_path)


class TestIsVendored:
    def test_node_modules_excluded(self):
        assert is_vendored("frontend/node_modules/react/index.js")

    def test_lockfile_excluded(self):
        assert is_vendored("package-lock.json")
        assert is_vendored("backend/poetry.lock")

    def test_minified_excluded(self):
        assert is_vendored("static/app.min.js")

    def test_normal_source_not_excluded(self):
        assert not is_vendored("backend/analyzer.py")
        assert not is_vendored("src/components/App.tsx")


class TestListSourceFiles:
    def test_lists_tracked_source_excludes_vendored(self, repo):
        _commit_file(repo, "a.py", "print('a')\n", ALICE, "add a")
        _commit_file(repo, "node_modules/dep.js", "x\n", ALICE, "vendor")
        _commit_file(repo, "package-lock.json", "{}\n", ALICE, "lock")
        _commit_file(repo, "notes.md", "hi\n", ALICE, "docs")  # not an ownership ext

        files = list_source_files(repo.working_tree_dir)
        assert "a.py" in files
        assert "node_modules/dep.js" not in files
        assert "package-lock.json" not in files
        assert "notes.md" not in files


class TestBuildOwnership:
    def test_ownership_attributed_per_author(self, repo):
        _commit_file(repo, "a.py", "l1\nl2\nl3\n", ALICE, "alice writes a")
        _commit_file(repo, "b.py", "x1\nx2\n", BOB, "bob writes b")

        ownership = build_ownership(repo.working_tree_dir)
        assert ownership["alice@example.com"].owned_lines == 3
        assert ownership["bob@example.com"].owned_lines == 2
        assert "a.py" in ownership["alice@example.com"].files

    def test_overwritten_lines_transfer_ownership(self, repo):
        _commit_file(repo, "a.py", "l1\nl2\nl3\n", ALICE, "alice")
        # Bob rewrites the whole file — he now owns the surviving lines.
        _commit_file(repo, "a.py", "b1\nb2\nb3\n", BOB, "bob rewrites")

        ownership = build_ownership(repo.working_tree_dir)
        assert ownership.get("alice@example.com", OwnershipRecord()).owned_lines == 0
        assert ownership["bob@example.com"].owned_lines == 3

    def test_vendored_files_not_counted(self, repo):
        _commit_file(repo, "a.py", "l1\n", ALICE, "alice")
        _commit_file(repo, "node_modules/big.js", "x\n" * 100, BOB, "bob vendors")

        ownership = build_ownership(repo.working_tree_dir)
        assert "bob@example.com" not in ownership


class TestAggregateEffort:
    def test_sums_per_author(self):
        events = [
            EffortEvent("c1", "alice@example.com", "alice@example.com", 1.0, "a.py", 10, 2),
            EffortEvent("c2", "alice@example.com", "alice@example.com", 2.0, "a.py", 5, 1),
            EffortEvent("c3", "bob@example.com", "bob@example.com", 3.0, "b.py", 4, 0),
        ]
        agg = aggregate_effort(events)
        assert agg["alice@example.com"]["added"] == 15
        assert agg["alice@example.com"]["deleted"] == 3
        assert agg["alice@example.com"]["commits"] == 2
        assert agg["bob@example.com"]["added"] == 4


class TestCombine:
    def test_percentages_and_divergence(self):
        ownership = {
            "alice@example.com": OwnershipRecord(owned_lines=90, files={"a.py"}),
            "bob@example.com": OwnershipRecord(owned_lines=10, files={"b.py"}),
        }
        effort = {
            "alice@example.com": {"added": 50, "deleted": 0, "commits": 5},
            "bob@example.com": {"added": 50, "deleted": 0, "commits": 5},
        }
        profile = combine(ownership, effort)
        assert profile["alice@example.com"]["ownership_pct"] == 90.0
        assert profile["alice@example.com"]["effort_pct"] == 50.0
        # Alice owns more than she churned → negative divergence.
        assert profile["alice@example.com"]["divergence"] == -40.0
        # Bob churned as much as Alice but little survives → positive divergence.
        assert profile["bob@example.com"]["divergence"] == 40.0

    def test_owner_with_no_effort_log(self):
        ownership = {"alice@example.com": OwnershipRecord(owned_lines=10, files={"a.py"})}
        profile = combine(ownership, {})
        assert profile["alice@example.com"]["ownership_pct"] == 100.0
        assert profile["alice@example.com"]["effort_pct"] == 0.0

    def test_empty_inputs(self):
        assert combine({}, {}) == {}
