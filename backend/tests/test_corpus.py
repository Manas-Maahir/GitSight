import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from eval.corpus import (
    CorpusEntry,
    evaluate_corpus,
    load_manifest,
    parse_entry,
    validate_entry,
)


class TestValidation:
    def test_valid_entry(self):
        raw = {"repo_url": "https://github.com/a/b", "roles": {"Alice": "Major Contributor"},
               "flags": {"Alice": ["bulk_paste"]}}
        assert validate_entry(raw) == []

    def test_missing_repo_url(self):
        assert "missing 'repo_url'" in validate_entry({"roles": {}})

    def test_invalid_role(self):
        errs = validate_entry({"repo_url": "u", "roles": {"Alice": "Rockstar"}})
        assert any("invalid role" in e for e in errs)

    def test_invalid_flag(self):
        errs = validate_entry({"repo_url": "u", "flags": {"Alice": ["plagiarism"]}})
        assert any("invalid flag" in e for e in errs)

    def test_flags_must_be_list(self):
        errs = validate_entry({"repo_url": "u", "flags": {"Alice": "bulk_paste"}})
        assert any("must be a list" in e for e in errs)


class TestParseAndLoad:
    def test_parse_entry_sets_defaults(self):
        e = parse_entry({"repo_url": "u"})
        assert e.name == "u" and e.roles == {} and e.flags == {}

    def test_flags_parsed_as_sets(self):
        e = parse_entry({"repo_url": "u", "flags": {"A": ["bulk_paste", "deadline_spike"]}})
        assert e.flags["A"] == {"bulk_paste", "deadline_spike"}

    def test_load_manifest_roundtrip(self, tmp_path):
        manifest = {
            "repositories": [
                {"name": "r1", "repo_url": "https://github.com/a/b",
                 "roles": {"Alice": "Major Contributor"}, "flags": {}},
            ]
        }
        p = tmp_path / "m.json"
        p.write_text(json.dumps(manifest), encoding="utf-8")
        entries = load_manifest(str(p))
        assert len(entries) == 1
        assert entries[0].name == "r1"

    def test_load_manifest_rejects_invalid(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps([{"repo_url": "u", "roles": {"A": "Nope"}}]), encoding="utf-8")
        with pytest.raises(ValueError):
            load_manifest(str(p))


class TestEvaluateCorpus:
    def test_perfect_prediction(self):
        entries = [
            CorpusEntry("u1", "r1", roles={"Alice": "Major Contributor", "Bob": "Free Rider"},
                        flags={"Bob": {"deadline_spike"}}),
        ]

        def predict(entry):
            return ({"Alice": "Major Contributor", "Bob": "Free Rider"},
                    {"Alice": set(), "Bob": {"deadline_spike"}})

        report = evaluate_corpus(entries, predict=predict)
        assert report["overall"]["roles"]["accuracy"] == 1.0
        assert report["overall"]["flags"]["recall"] == 1.0
        assert report["overall"]["flags"]["precision"] == 1.0

    def test_scores_disagreement(self):
        entries = [
            CorpusEntry("u1", "r1", roles={"Alice": "Major Contributor", "Bob": "Free Rider"},
                        flags={"Bob": {"bulk_paste"}}),
        ]

        def predict(entry):
            # Wrong on Bob's role; misses his flag; invents a flag for Alice.
            return ({"Alice": "Major Contributor", "Bob": "Minor Contributor"},
                    {"Alice": {"deadline_spike"}, "Bob": set()})

        report = evaluate_corpus(entries, predict=predict)
        assert report["overall"]["roles"]["accuracy"] == 0.5
        flags = report["overall"]["flags"]
        assert flags["fn"] == 1  # missed Bob's bulk_paste
        assert flags["fp"] == 1  # invented Alice's deadline_spike

    def test_aggregates_across_repos(self):
        entries = [
            CorpusEntry("u1", "r1", roles={"A": "Major Contributor"}),
            CorpusEntry("u2", "r2", roles={"A": "Free Rider"}),
        ]

        def predict(entry):
            return ({"A": "Major Contributor"}, {})

        report = evaluate_corpus(entries, predict=predict)
        # Same author name in two repos must not collide (namespaced by repo).
        assert report["overall"]["roles"]["total"] == 2
        assert report["overall"]["roles"]["accuracy"] == 0.5
