import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import git
import pytest
from git import Actor

import config
import store
from analyzer import get_remote_head


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "get_db_path", lambda: db_path)
    store.init_db()
    return db_path


def _payload(authors):
    return {"status": "success", "repo": "https://github.com/x/y", "authors": authors}


class TestCache:
    def test_miss_then_hit(self, db):
        assert store.get_cached("https://github.com/x/y", "sha1") is None
        store.save_analysis("https://github.com/x/y", "sha1", _payload([]))
        hit = store.get_cached("https://github.com/x/y", "sha1")
        assert hit is not None
        assert "analysis_id" in hit

    def test_different_sha_is_a_miss(self, db):
        store.save_analysis("https://github.com/x/y", "sha1", _payload([]))
        assert store.get_cached("https://github.com/x/y", "sha2") is None

    def test_resave_same_key_updates(self, db):
        id1 = store.save_analysis("u", "s", _payload([{"author": "A"}]))
        id2 = store.save_analysis("u", "s", _payload([{"author": "B"}]))
        assert id1 == id2  # upsert, not a new row
        assert store.get_cached("u", "s")["authors"][0]["author"] == "B"


class TestOverrides:
    def test_record_and_fetch(self, db):
        aid = store.save_analysis("u", "s", _payload([{"author": "Alice", "score": 10, "role": "Minor Contributor"}]))
        store.record_override(aid, "Alice", "Major Contributor", "did the architecture")
        rows = store.get_overrides(aid)
        assert len(rows) == 1
        assert rows[0]["instructor_role"] == "Major Contributor"
        assert rows[0]["note"] == "did the architecture"

    def test_invalid_role_rejected(self, db):
        aid = store.save_analysis("u", "s", _payload([]))
        with pytest.raises(ValueError):
            store.record_override(aid, "Alice", "Rockstar")


class TestReviews:
    def test_agreement_recorded(self, db):
        authors = [{"author": "Alice", "score": 80.0, "role": "Major Contributor"}]
        aid = store.save_analysis("u", "s", _payload(authors))
        result = store.record_review(aid, "Alice", "Major Contributor")
        assert result["agreed"] is True
        rows = store.get_reviews(aid)
        assert len(rows) == 1 and rows[0]["agreed"] == 1

    def test_disagreement_recorded(self, db):
        authors = [{"author": "Bob", "score": 10.0, "role": "Free Rider"}]
        aid = store.save_analysis("u", "s", _payload(authors))
        result = store.record_review(aid, "Bob", "Minor Contributor")
        assert result["agreed"] is False
        assert result["system_role"] == "Free Rider"

    def test_unknown_author_rejected(self, db):
        aid = store.save_analysis("u", "s", _payload([{"author": "A", "role": "Minor Contributor"}]))
        with pytest.raises(ValueError):
            store.record_review(aid, "Ghost", "Major Contributor")

    def test_invalid_role_rejected(self, db):
        aid = store.save_analysis("u", "s", _payload([{"author": "A", "role": "Minor Contributor"}]))
        with pytest.raises(ValueError):
            store.record_review(aid, "A", "Wizard")

    def test_reviews_capture_both_classes(self, db):
        authors = [{"author": "A", "score": 80.0, "role": "Major Contributor"},
                   {"author": "B", "score": 5.0, "role": "Free Rider"}]
        aid = store.save_analysis("u", "s", _payload(authors))
        store.record_review(aid, "A", "Major Contributor")   # agree
        store.record_review(aid, "B", "Minor Contributor")   # disagree
        rows = store.get_reviews()
        assert {r["agreed"] for r in rows} == {0, 1}


class TestCalibrationModelPersistence:
    def test_save_and_get(self, db):
        store.save_calibration_model("global", '{"a": 1}', n_labels=50, ece=0.07)
        m = store.get_calibration_model("global")
        assert m["n_labels"] == 50 and m["ece"] == 0.07

    def test_upsert(self, db):
        store.save_calibration_model("global", '{"v": 1}', 10, 0.2)
        store.save_calibration_model("global", '{"v": 2}', 20, 0.1)
        m = store.get_calibration_model("global")
        assert m["n_labels"] == 20 and '"v": 2' in m["model_json"]

    def test_missing_scope(self, db):
        assert store.get_calibration_model("nope") is None


class TestCalibration:
    def test_empty_report(self, db):
        report = store.calibration_report()
        assert report["total_overrides"] == 0
        assert report["agreement"] is None

    def test_agreement_and_cutoffs(self, db):
        authors = [
            {"author": "Alice", "score": 8.0, "role": "Free Rider"},
            {"author": "Bob", "score": 60.0, "role": "Major Contributor"},
        ]
        aid = store.save_analysis("u", "s", _payload(authors))
        # Instructor agrees Bob is Major, but disagrees on Alice (calls her Major).
        store.record_override(aid, "Bob", "Major Contributor")
        store.record_override(aid, "Alice", "Major Contributor")
        report = store.calibration_report()
        assert report["total_overrides"] == 2
        assert report["agreement"] == 0.5
        assert report["suggested_cutoffs"]["major_min_score"] == 8.0


class TestRemoteHead:
    def test_local_repo_head(self, tmp_path):
        repo = git.Repo.init(tmp_path)
        actor = Actor("A", "a@x.com")
        f = tmp_path / "a.txt"
        f.write_text("hi\n")
        repo.index.add(["a.txt"])
        c = repo.index.commit("init", author=actor, committer=actor)
        head = get_remote_head(str(tmp_path))
        assert head == c.hexsha

    def test_bad_remote_returns_none(self, tmp_path):
        assert get_remote_head(str(tmp_path / "does-not-exist")) is None
