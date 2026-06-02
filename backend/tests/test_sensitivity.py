import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from eval import sensitivity


class TestSweep:
    def test_restores_config_after_sweep(self):
        original = config.INTEGRITY_PASTE_FLOOR
        sensitivity.sweep("INTEGRITY_PASTE_FLOOR", [100, 999], sensitivity._eval_paste)
        assert config.INTEGRITY_PASTE_FLOOR == original

    def test_paste_floor_has_a_cliff(self):
        rows = sensitivity.sweep(
            "INTEGRITY_PASTE_FLOOR", [300, 800], sensitivity._eval_paste)
        by_val = {r["value"]: r for r in rows}
        assert by_val[300]["detect"] == 1   # default plateau detects
        assert by_val[800]["detect"] == 0   # raising past the paste size misses it

    def test_no_false_positive_on_control(self):
        rows = sensitivity.sweep(
            "INTEGRITY_PASTE_FLOOR", [100, 300, 600], sensitivity._eval_paste)
        assert all(r["fp"] == 0 for r in rows)

    def test_median_mult_is_robust(self):
        rows = sensitivity.sweep(
            "INTEGRITY_PASTE_MEDIAN_MULT", [2, 5, 12, 20], sensitivity._eval_paste)
        assert all(r["detect"] == 1 and r["fp"] == 0 for r in rows)

    def test_slope_present_after_first_point(self):
        rows = sensitivity.sweep(
            "INTEGRITY_PASTE_FLOOR", [300, 800], sensitivity._eval_paste)
        assert "slope" not in rows[0]
        assert "slope" in rows[1]


class TestReport:
    def test_report_covers_key_thresholds(self):
        rep = sensitivity.report()
        assert {"INTEGRITY_PASTE_FLOOR", "INTEGRITY_DEADLINE_RATIO",
                "ROLE_MAJOR_THRESHOLD", "ROLE_FREE_RIDER_THRESHOLD"} <= set(rep)

    def test_report_does_not_mutate_config(self):
        before = (config.INTEGRITY_PASTE_FLOOR, config.ROLE_MAJOR_THRESHOLD,
                  config.INTEGRITY_DEADLINE_RATIO)
        sensitivity.report()
        after = (config.INTEGRITY_PASTE_FLOOR, config.ROLE_MAJOR_THRESHOLD,
                 config.INTEGRITY_DEADLINE_RATIO)
        assert before == after
