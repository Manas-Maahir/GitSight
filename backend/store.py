"""
Persistence, caching, and calibration (SQLite).

Two tables:

* ``analyses`` — one row per (repo_url, HEAD sha). Acts as the result cache:
  an unchanged repository is never re-analysed.
* ``overrides`` — instructor corrections to a verdict. These feed the calibration
  report, which *suggests* (never silently applies) threshold adjustments so a
  course's grading norms can be made explicit and reviewable.

Connections are opened per call against ``config.get_db_path()`` so the module is
safe to use from FastAPI's thread pool without shared-connection hazards.
"""

from __future__ import annotations

import json
import sqlite3
import time

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_url     TEXT NOT NULL,
    head_sha     TEXT NOT NULL,
    created_at   REAL NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(repo_url, head_sha)
);
CREATE TABLE IF NOT EXISTS overrides (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id     INTEGER NOT NULL,
    author          TEXT NOT NULL,
    instructor_role TEXT NOT NULL,
    note            TEXT DEFAULT '',
    created_at      REAL NOT NULL,
    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
);
CREATE TABLE IF NOT EXISTS reviews (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id      INTEGER NOT NULL,
    author           TEXT NOT NULL,
    system_role      TEXT NOT NULL,
    instructor_role  TEXT NOT NULL,
    agreed           INTEGER NOT NULL,
    score            REAL,
    confidence_value REAL,
    reviewer         TEXT DEFAULT '',
    note             TEXT DEFAULT '',
    created_at       REAL NOT NULL,
    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
);
CREATE TABLE IF NOT EXISTS calibration_models (
    scope        TEXT PRIMARY KEY,
    model_json   TEXT NOT NULL,
    n_labels     INTEGER NOT NULL,
    ece          REAL,
    updated_at   REAL NOT NULL
);
"""

_VALID_ROLES = {"Major Contributor", "Minor Contributor", "Free Rider"}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ── Caching ──────────────────────────────────────────────────────────────────

def get_cached(repo_url: str, head_sha: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, payload_json FROM analyses WHERE repo_url = ? AND head_sha = ?",
            (repo_url, head_sha),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    payload = json.loads(row["payload_json"])
    payload["analysis_id"] = row["id"]
    return payload


def save_analysis(repo_url: str, head_sha: str, payload: dict) -> int:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO analyses (repo_url, head_sha, created_at, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(repo_url, head_sha)
            DO UPDATE SET payload_json = excluded.payload_json,
                          created_at  = excluded.created_at
            """,
            (repo_url, head_sha, time.time(), json.dumps(payload)),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM analyses WHERE repo_url = ? AND head_sha = ?",
            (repo_url, head_sha),
        ).fetchone()
        return int(row["id"])
    finally:
        conn.close()


def get_analysis(analysis_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, payload_json FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    payload = json.loads(row["payload_json"])
    payload["analysis_id"] = row["id"]
    return payload


# ── Instructor overrides ─────────────────────────────────────────────────────

def record_override(
    analysis_id: int, author: str, instructor_role: str, note: str = ""
) -> None:
    if instructor_role not in _VALID_ROLES:
        raise ValueError(f"invalid role: {instructor_role!r}")
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO overrides (analysis_id, author, instructor_role, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (analysis_id, author, instructor_role, note, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_overrides(analysis_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT author, instructor_role, note, created_at FROM overrides "
            "WHERE analysis_id = ? ORDER BY created_at",
            (analysis_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ── Reviews (confirm OR override — the unbiased calibration label source) ─────

def record_review(
    analysis_id: int, author: str, instructor_role: str,
    reviewer: str = "", note: str = "",
) -> dict:
    """
    Record an instructor decision on one author — agreement *or* correction.

    Unlike ``overrides`` (which only captured disagreements and would miscalibrate
    a model), reviews capture both, so the label distribution is unbiased. The
    system role and score are read from the stored analysis payload.
    """
    if instructor_role not in _VALID_ROLES:
        raise ValueError(f"invalid role: {instructor_role!r}")
    analysis = get_analysis(analysis_id)
    if analysis is None:
        raise ValueError(f"unknown analysis_id: {analysis_id}")
    scored = next((a for a in analysis.get("authors", []) if a["author"] == author), None)
    if scored is None:
        raise ValueError(f"author {author!r} not in analysis {analysis_id}")

    system_role = scored.get("role")
    agreed = int(system_role == instructor_role)
    confidence_value = ((scored.get("explanation") or {}).get("trust") or {}).get("value")
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO reviews
                (analysis_id, author, system_role, instructor_role, agreed, score,
                 confidence_value, reviewer, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (analysis_id, author, system_role, instructor_role, agreed,
             scored.get("score"), confidence_value, reviewer, note, time.time()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"system_role": system_role, "instructor_role": instructor_role, "agreed": bool(agreed)}


def get_reviews(analysis_id: int | None = None) -> list[dict]:
    conn = _connect()
    try:
        if analysis_id is None:
            rows = conn.execute(
                "SELECT analysis_id, author, system_role, instructor_role, agreed, score, "
                "confidence_value, reviewer, note, created_at FROM reviews ORDER BY created_at"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT analysis_id, author, system_role, instructor_role, agreed, score, "
                "confidence_value, reviewer, note, created_at FROM reviews WHERE analysis_id = ? ORDER BY created_at",
                (analysis_id,),
            ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ── Calibration model persistence ─────────────────────────────────────────────

def save_calibration_model(scope: str, model_json: str, n_labels: int, ece: float | None) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO calibration_models (scope, model_json, n_labels, ece, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(scope) DO UPDATE SET
                model_json = excluded.model_json, n_labels = excluded.n_labels,
                ece = excluded.ece, updated_at = excluded.updated_at
            """,
            (scope, model_json, n_labels, ece, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_calibration_model(scope: str = "global") -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT scope, model_json, n_labels, ece, updated_at FROM calibration_models "
            "WHERE scope = ?", (scope,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


# ── Calibration ──────────────────────────────────────────────────────────────

def _labeled_pairs(analysis_id: int | None) -> list[dict]:
    """Join overrides with their analysis payload to get (score, system_role, instructor_role)."""
    conn = _connect()
    try:
        if analysis_id is None:
            rows = conn.execute(
                "SELECT analysis_id, author, instructor_role FROM overrides"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT analysis_id, author, instructor_role FROM overrides WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchall()
        payload_cache: dict[int, dict] = {}
        pairs: list[dict] = []
        for r in rows:
            aid = r["analysis_id"]
            if aid not in payload_cache:
                prow = conn.execute(
                    "SELECT payload_json FROM analyses WHERE id = ?", (aid,)
                ).fetchone()
                payload_cache[aid] = json.loads(prow["payload_json"]) if prow else {}
            authors = {a["author"]: a for a in payload_cache[aid].get("authors", [])}
            scored = authors.get(r["author"])
            if scored is None:
                continue
            pairs.append({
                "author": r["author"],
                "score": scored.get("score"),
                "system_role": scored.get("role"),
                "instructor_role": r["instructor_role"],
            })
        return pairs
    finally:
        conn.close()


def calibration_report(analysis_id: int | None = None) -> dict:
    """
    Summarise instructor agreement and *suggest* score cutoffs.

    The suggestion is advisory: the largest impact score an instructor labelled a
    Free Rider, and the smallest they labelled a Major Contributor — the band where
    the automated thresholds disagree with human judgement.
    """
    pairs = [p for p in _labeled_pairs(analysis_id) if p["score"] is not None]
    total = len(pairs)
    if total == 0:
        return {"total_overrides": 0, "agreement": None, "suggested_cutoffs": {}, "pairs": []}

    agree = sum(1 for p in pairs if p["system_role"] == p["instructor_role"])
    free_scores = [p["score"] for p in pairs if p["instructor_role"] == "Free Rider"]
    major_scores = [p["score"] for p in pairs if p["instructor_role"] == "Major Contributor"]

    suggested = {}
    if free_scores:
        suggested["free_rider_max_score"] = round(max(free_scores), 2)
    if major_scores:
        suggested["major_min_score"] = round(min(major_scores), 2)

    return {
        "total_overrides": total,
        "agreement": round(agree / total, 3),
        "disagreements": total - agree,
        "suggested_cutoffs": suggested,
        "pairs": pairs,
    }
