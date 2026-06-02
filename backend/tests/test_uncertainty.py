import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trust.uncertainty import _percentile, ownership_intervals


def _lines(author, n):
    return {i: author for i in range(n)}


class TestPercentile:
    def test_bounds_and_midpoint(self):
        s = [0.0, 10.0, 20.0, 30.0, 40.0]
        assert _percentile(s, 0) == 0.0
        assert _percentile(s, 100) == 40.0
        assert _percentile(s, 50) == 20.0

    def test_empty(self):
        assert _percentile([], 50) == 0.0


class TestOwnershipIntervals:
    def test_empty_input(self):
        assert ownership_intervals({}) == {}

    def test_single_file_is_insufficient(self):
        # One file → ownership cannot be bounded → full [0,100], flagged.
        iv = ownership_intervals({"a.py": _lines("alice", 50)})
        assert iv["alice"]["insufficient"] is True
        assert iv["alice"]["lo"] == 0.0 and iv["alice"]["hi"] == 100.0
        assert iv["alice"]["point"] == 100.0

    def test_point_estimate_matches_share(self):
        lo = {f"f{i}.py": _lines("alice", 8) for i in range(5)}
        lo.update({f"g{i}.py": _lines("bob", 2) for i in range(5)})
        iv = ownership_intervals(lo)
        # Alice owns 40 of 50 lines = 80%.
        assert iv["alice"]["point"] == 80.0
        assert iv["bob"]["point"] == 20.0

    def test_more_balanced_files_narrows_interval(self):
        # Concentrated: alice owns one big file, bob many small → alice's estimate
        # is fragile (wide CI). Balanced: many equal files → tighter CI.
        concentrated = {"big.py": _lines("alice", 100)}
        concentrated.update({f"s{i}.py": _lines("bob", 5) for i in range(8)})
        balanced = {f"a{i}.py": _lines("alice", 10) for i in range(8)}
        balanced.update({f"b{i}.py": _lines("bob", 10) for i in range(8)})

        iv_conc = ownership_intervals(concentrated)
        iv_bal = ownership_intervals(balanced)
        assert iv_conc["alice"]["ci_width"] > iv_bal["alice"]["ci_width"]

    def test_interval_brackets_point(self):
        lo = {f"f{i}.py": _lines("alice", 8) for i in range(5)}
        lo.update({f"g{i}.py": _lines("bob", 2) for i in range(5)})
        iv = ownership_intervals(lo)
        a = iv["alice"]
        assert a["lo"] <= a["point"] <= a["hi"]

    def test_deterministic_with_seed(self):
        lo = {f"f{i}.py": _lines("alice", 7) for i in range(4)}
        lo.update({f"g{i}.py": _lines("bob", 3) for i in range(4)})
        assert ownership_intervals(lo, seed=1) == ownership_intervals(lo, seed=1)

    def test_n_files_counted(self):
        lo = {"a.py": _lines("alice", 5), "b.py": _lines("alice", 5),
              "c.py": _lines("bob", 5)}
        iv = ownership_intervals(lo)
        assert iv["alice"]["n_files"] == 2
        assert iv["bob"]["n_files"] == 1
