import asyncio
import logging
import os
import time
import uuid

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import explain
import store
from analyzer import analyze_repository, get_remote_head, validate_github_url
from scoring import calculate_scores
from trust import calibration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GitSight API",
    description="Analyse GitHub repository contributions by commit history and code quality.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

store.init_db()

# In-process job registry for the async analysis API. Single-process only — a
# multi-worker deployment should move this to Redis/RQ (see the roadmap).
_jobs: dict[str, dict] = {}

# Ordered pipeline stages surfaced to the UI as live progress. Keys are emitted
# by analyzer.analyze_repository / run_analysis at the genuine compute
# boundaries; labels are the human-facing copy shown in the progress stepper.
PIPELINE_STAGES: list[tuple[str, str]] = [
    ("cloning", "Cloning repository"),
    ("parsing_history", "Parsing git history"),
    ("attribution", "Attribution analysis"),
    ("quality", "Code quality"),
    ("ownership_modeling", "Ownership modeling"),
    ("integrity", "Integrity forensics"),
    ("scoring", "Scoring contributions"),
    ("explaining", "Generating explanations"),
]
_STAGE_INDEX = {key: i for i, (key, _label) in enumerate(PIPELINE_STAGES)}


def _initial_stage_state() -> dict:
    """Fresh stage-tracking block for a newly created job."""
    return {
        "stage": None,
        "stage_index": 0,
        "total_stages": len(PIPELINE_STAGES),
        "stages": [
            {"key": key, "label": label, "state": "pending"}
            for key, label in PIPELINE_STAGES
        ],
        "meta": {},
        "started_at": time.time(),
        "updated_at": time.time(),
    }


def _make_progress(job_id: str):
    """Return an ``on_stage(key, meta)`` callback that records real progress
    for *job_id* into the in-process job registry."""

    def on_stage(key: str, meta: dict | None = None) -> None:
        job = _jobs.get(job_id)
        if job is None:
            return
        idx = _STAGE_INDEX.get(key)
        if idx is None:
            return
        for i, stage in enumerate(job["stages"]):
            if i < idx:
                stage["state"] = "done"
            elif i == idx:
                stage["state"] = "active"
            else:
                stage["state"] = "pending"
        job["stage"] = key
        job["stage_index"] = idx
        if meta:
            job["meta"] = meta
        job["updated_at"] = time.time()

    return on_stage


class RepoRequest(BaseModel):
    url: str


class OverrideRequest(BaseModel):
    analysis_id: int
    author: str
    instructor_role: str
    note: str = ""


class ReviewRequest(BaseModel):
    analysis_id: int
    author: str
    instructor_role: str
    reviewer: str = ""
    note: str = ""


def _load_calibrator(scope: str = "global"):
    """Load the persisted calibration model, or an empty (cold-start) calibrator."""
    record = store.get_calibration_model(scope)
    if record:
        return calibration.Calibrator.from_json(record["model_json"])
    return calibration.Calibrator()


def run_analysis(url: str, on_stage=None) -> dict:
    """
    Cache-aware analysis (blocking). Returns the full response payload.

    Checks the (repo_url, HEAD sha) cache first; only clones and analyses on a
    miss, then persists the result. Safe to call inside ``asyncio.to_thread``.

    *on_stage* is an optional progress callback (see analyzer.StageCallback)
    used by the async job API to stream live pipeline stages to the UI.
    """
    stage = on_stage if on_stage is not None else (lambda _key, _meta=None: None)
    head_sha = get_remote_head(url)
    if config.CACHE_ENABLED and head_sha:
        cached = store.get_cached(url, head_sha)
        if cached is not None:
            cached["cached"] = True
            return cached

    data = analyze_repository(url, on_stage=on_stage)
    stage("scoring")
    scored = calculate_scores(data["stats"])
    stage("explaining")
    authors = explain.annotate(scored, data.get("reliability"), _load_calibrator())
    payload = {
        "status": "success",
        "repo": url,
        "head_sha": head_sha,
        "cached": False,
        "total_commits": data["total_commits"],
        "truncated": data.get("truncated", False),
        "reliability": data.get("reliability"),
        "authors": authors,
        "timeline": data["timeline"],
    }
    if config.CACHE_ENABLED and head_sha:
        payload["analysis_id"] = store.save_analysis(url, head_sha, payload)
    return payload


def _validate_url_or_400(url: str) -> None:
    if not url or not validate_github_url(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub URL. Expected format: https://github.com/owner/repo",
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "1.1.0"}


@app.post("/api/analyze")
async def analyze_repo(req: RepoRequest) -> dict:
    _validate_url_or_400(req.url)
    try:
        return await asyncio.to_thread(run_analysis, req.url)
    except RuntimeError as exc:
        logger.warning("Analysis failed for %s: %s", req.url, exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected error analysing %s: %s", req.url, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again or file an issue.",
        )


def _finish_stages(job_id: str, state: str) -> None:
    """Mark every stage of *job_id* as done/error so the UI settles cleanly."""
    job = _jobs.get(job_id)
    if not job or "stages" not in job:
        return
    for stage in job["stages"]:
        if state == "done":
            stage["state"] = "done"
        elif stage["state"] == "active":
            stage["state"] = "error"
    job["updated_at"] = time.time()


async def _run_job(job_id: str, url: str) -> None:
    _jobs[job_id]["status"] = "running"
    on_stage = _make_progress(job_id)
    try:
        result = await asyncio.to_thread(run_analysis, url, on_stage)
        _finish_stages(job_id, "done")
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = result
    except RuntimeError as exc:
        _finish_stages(job_id, "error")
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(exc)
    except Exception as exc:
        logger.error("Job %s failed for %s: %s", job_id, url, exc, exc_info=True)
        _finish_stages(job_id, "error")
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = "An unexpected error occurred."


@app.post("/api/jobs")
async def create_job(req: RepoRequest) -> dict:
    """Start analysis in the background; poll GET /api/jobs/{id} for the result."""
    _validate_url_or_400(req.url)
    job_id = uuid.uuid4().hex
    _jobs[job_id] = {"status": "pending", **_initial_stage_state()}
    asyncio.create_task(_run_job(job_id, req.url))
    return {"job_id": job_id, "status": "pending"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    return {"job_id": job_id, **job}


@app.post("/api/override")
def add_override(req: OverrideRequest) -> dict:
    """Record an instructor's correction to a verdict (feeds calibration)."""
    if store.get_analysis(req.analysis_id) is None:
        raise HTTPException(status_code=404, detail="Unknown analysis id.")
    try:
        store.record_override(req.analysis_id, req.author, req.instructor_role, req.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}


@app.post("/api/review")
def add_review(req: ReviewRequest) -> dict:
    """
    Record an instructor decision (confirm OR correct) for one author. This is the
    unbiased label source for calibration — it captures agreements, not only
    disagreements.
    """
    try:
        result = store.record_review(
            req.analysis_id, req.author, req.instructor_role, req.reviewer, req.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", **result}


@app.get("/api/calibration")
def calibration_summary(analysis_id: int | None = None) -> dict:
    """Instructor-agreement summary and advisory cutoff suggestions."""
    return store.calibration_report(analysis_id)


@app.post("/api/calibration/train")
def calibration_train() -> dict:
    """Refit the confidence calibrator from all instructor reviews and persist it."""
    cal, metrics = calibration.train_from_reviews(store.get_reviews())
    if cal is not None:
        store.save_calibration_model("global", cal.to_json(), metrics["n"], metrics["ece"])
    return metrics


@app.get("/api/calibration/metrics")
def calibration_metrics() -> dict:
    """
    Current calibration quality (ECE, Brier, reliability diagram) on the review set.

    NOTE: these are in-sample metrics — optimistic until a held-out evaluation is run
    on a larger label set. The regime field reports whether confidence is calibrated
    or still cold-start.
    """
    _cal, metrics = calibration.train_from_reviews(store.get_reviews())
    metrics["model_persisted"] = store.get_calibration_model("global") is not None
    return metrics


static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # The Vite build references hashed assets at absolute /assets/* paths;
    # serve them directly so index.html resolves without a base-path rewrite.
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def serve_index() -> FileResponse:
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found.")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    icon = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(icon):
        return FileResponse(icon)
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
