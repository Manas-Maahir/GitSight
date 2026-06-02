import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eval import scenarios
from eval.metrics import flag_metrics, role_metrics
from eval.runner import evaluate, run_scenario


class TestMetrics:
    def test_role_accuracy(self):
        m = role_metrics({"A": "Major Contributor", "B": "Free Rider"},
                         {"A": "Major Contributor", "B": "Minor Contributor"})
        assert m["accuracy"] == 0.5
        assert m["errors"][0]["author"] == "B"

    def test_flag_precision_recall(self):
        predicted = {"A": {"bulk_paste"}, "B": {"deadline_spike"}}
        expected = {"A": {"bulk_paste"}, "B": set()}
        m = flag_metrics(predicted, expected)
        assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 0
        assert m["precision"] == 0.5
        assert m["recall"] == 1.0

    def test_flag_metrics_no_data(self):
        m = flag_metrics({}, {})
        assert m["precision"] is None and m["recall"] is None


class TestScenariosDetected:
    def _flags(self, build):
        _roles, flags, gt = run_scenario(build)
        return flags, gt

    def test_free_rider_roles(self):
        roles, _flags, gt = run_scenario(scenarios.free_rider)
        assert roles == gt.roles

    def test_deadline_spike_detected(self):
        flags, gt = self._flags(scenarios.deadline_dumper)
        assert "deadline_spike" in flags["Bob"]

    def test_bulk_paste_detected(self):
        flags, gt = self._flags(scenarios.bulk_paster)
        assert "bulk_paste" in flags["Bob"]

    def test_authorship_laundering_detected(self):
        flags, gt = self._flags(scenarios.laundering)
        assert "authorship_laundering" in flags["Carol"]

    def test_balanced_team_has_no_flags(self):
        flags, _gt = self._flags(scenarios.balanced_team)
        assert all(len(v) == 0 for v in flags.values())


class TestFullEvaluation:
    def test_overall_metrics_are_perfect_on_synthetic_set(self):
        report = evaluate()
        assert report["overall"]["roles"]["accuracy"] == 1.0
        # Every injected flag caught, no spurious flags.
        assert report["overall"]["flags"]["recall"] == 1.0
        assert report["overall"]["flags"]["precision"] == 1.0
