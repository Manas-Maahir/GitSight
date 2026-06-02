import logging
import os
import re
import shutil
import stat
import sys
from typing import Callable, Optional

# Progress callback: ``on_stage(stage_key, meta)`` where *meta* is an optional
# dict of details (e.g. {"commits": 240}). Used to surface live pipeline stages
# to the async job API; a no-op when analysis runs synchronously.
StageCallback = Callable[[str, Optional[dict]], None]

import git
from git.exc import GitCommandError
from pydriller import Repository

import attribution
import config
import integrity
import quality
from trust import reliability, uncertainty

try:
    import radon.metrics
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False

try:
    import lizard
    LIZARD_AVAILABLE = True
except ImportError:
    LIZARD_AVAILABLE = False

logger = logging.getLogger(__name__)

_GITHUB_URL_RE = re.compile(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?/?$")


def validate_github_url(url: str) -> bool:
    return bool(_GITHUB_URL_RE.match(url))


def get_remote_head(repo_url: str) -> str | None:
    """
    Return the repository's HEAD commit sha without cloning (``git ls-remote``).

    Used as a cache key so an unchanged repo is never re-cloned or re-analysed.
    Returns None if the remote cannot be reached.
    """
    try:
        out = git.cmd.Git().ls_remote(repo_url, "HEAD")
    except Exception:
        return None
    out = (out or "").strip()
    return out.split()[0] if out else None


def _on_rm_error(func, path, _exc) -> None:
    """rmtree error handler: clear the read-only bit (Windows .git packs) and retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        logger.warning("Could not remove %s during clone cleanup", path)


def _safe_rmtree(path: str) -> None:
    """Remove a directory tree, tolerating read-only git objects on Windows."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=lambda f, p, e: _on_rm_error(f, p, e))
    else:  # pragma: no cover - older interpreters
        shutil.rmtree(path, onerror=_on_rm_error)


def calculate_quality(source_code: str) -> dict[str, float]:
    if not source_code or not source_code.strip():
        return {"overall": 100.0}

    # 1. Cyclomatic complexity — clamped so 1/cc never exceeds 100
    try:
        liz = lizard.analyze_file.analyze_source_code("temp.py", source_code)
        cc = max(liz.average_cyclomatic_complexity, 1.0)
    except Exception:
        cc = 1.0
    cc_score = min(100.0, (1.0 / cc) * 100.0)

    # 2. Maintainability index (radon returns 0-100; clamp for safety)
    try:
        mi = float(radon.metrics.mi_visit(source_code, True))
        mi = max(0.0, min(100.0, mi))
    except Exception:
        mi = 100.0

    # 3. Comment density
    lines = source_code.splitlines()
    total_lines = len(lines) or 1
    comment_lines = sum(
        1 for ln in lines
        if ln.strip().startswith(("#", "//", "/*", "*"))
    )
    cd_ratio = comment_lines / total_lines
    cd_score = min(100.0, (cd_ratio / config.QUALITY_CD_TARGET_RATIO) * 100.0)

    # 4. Linter heuristic — penalise overly long lines
    long_lines = sum(1 for ln in lines if len(ln) > config.QUALITY_MAX_LINE_LENGTH)
    linter_score = max(0.0, 100.0 - (long_lines / total_lines) * 200.0)

    # 5. Readability — penalise high average line length
    avg_len = sum(len(ln) for ln in lines) / total_lines
    readability = max(0.0, 100.0 - max(0.0, avg_len - config.QUALITY_IDEAL_LINE_LENGTH))

    overall = (
        cc_score * config.QUALITY_WEIGHT_CC
        + mi * config.QUALITY_WEIGHT_MI
        + cd_score * config.QUALITY_WEIGHT_CD
        + linter_score * config.QUALITY_WEIGHT_LINTER
        + readability * config.QUALITY_WEIGHT_READABILITY
    )
    return {"overall": min(100.0, overall)}


def _merge_author_by_email(
    stats: dict[str, dict],
    email_to_canonical: dict[str, str],
) -> dict[str, dict]:
    """Merge entries that share an email address into a single canonical name."""
    merged: dict[str, dict] = {}
    for name, data in stats.items():
        canonical = email_to_canonical.get(data.get("_email", ""), name)
        if canonical not in merged:
            merged[canonical] = {
                "commits": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "files_modified": 0,
                "files": set(),
            }
        m = merged[canonical]
        m["commits"] += data["commits"]
        m["lines_added"] += data["lines_added"]
        m["lines_deleted"] += data["lines_deleted"]
        m["files_modified"] += data["files_modified"]
        m["files"].update(data["files"])
    return merged


def analyze_repository(
    repo_url: str,
    deadline: float | None = None,
    on_stage: StageCallback | None = None,
) -> dict:
    """
    Clone *repo_url*, traverse its commits, and return per-author statistics
    plus a commit timeline.

    *deadline* (epoch seconds) sharpens the deadline-spike signal when known;
    otherwise it is inferred from the last commit.

    *on_stage* is an optional progress callback invoked at each genuine pipeline
    boundary (cloning, parsing, attribution, ...) so the async job API can stream
    real progress to the UI.

    The clone is always deleted on exit (even on error) to prevent unbounded
    disk growth.
    """
    stage = on_stage if on_stage is not None else (lambda _key, _meta=None: None)
    stats: dict[str, dict] = {}
    email_to_canonical: dict[str, str] = {}
    timeline: list[dict] = []
    events: list[attribution.EffortEvent] = []
    commit_messages: dict[str, str] = {}
    commit_meta: list[dict] = []
    ownership_records: dict[str, attribution.OwnershipRecord] = {}
    quality_acc_by_email: dict[str, dict] = {}
    ownership_iv: dict[str, dict] = {}
    truncated = False
    commit_count = 0

    clone_root = config.get_clone_root()
    repo_dir: str | None = None

    logger.info("Starting analysis for %s", repo_url)

    try:
        stage("cloning")
        repo_iter = Repository(repo_url, clone_repo_to=clone_root)

        for commit in repo_iter.traverse_commits():
            if commit_count == 0:
                stage("parsing_history", {"commits": 0})
            # Capture the on-disk repo path (cloned temp dir for remote URLs)
            # so the ownership pass can run git blame before cleanup.
            if repo_dir is None:
                try:
                    repo_dir = str(commit.project_path)
                except Exception:
                    repo_dir = None

            commit_count += 1
            if commit_count > config.MAX_COMMITS:
                truncated = True
                break

            # Periodic progress so long histories show live movement.
            if commit_count % 100 == 0:
                stage("parsing_history", {"commits": commit_count})

            author_name: str = commit.author.name or "Unknown"
            author_email: str = (commit.author.email or "").lower()

            # Build email → canonical-name mapping (first-seen wins)
            if author_email and author_email not in email_to_canonical:
                email_to_canonical[author_email] = author_name

            if author_name not in stats:
                stats[author_name] = {
                    "_email": author_email,
                    "commits": 0,
                    "lines_added": 0,
                    "lines_deleted": 0,
                    "files_modified": 0,
                    "files": set(),
                }

            commit_messages[commit.hash] = commit.msg or ""
            commit_meta.append({
                "sha": commit.hash,
                "author_email": author_email,
                "committer_email": (commit.committer.email or "").lower(),
                "author_ts": commit.author_date.timestamp(),
                "committer_ts": commit.committer_date.timestamp(),
                "msg": commit.msg or "",
                "added": commit.insertions,
                "deleted": commit.deletions,
                "files": commit.files,
            })

            entry = stats[author_name]
            entry["commits"] += 1
            entry["lines_added"] += commit.insertions
            entry["lines_deleted"] += commit.deletions
            entry["files_modified"] += commit.files

            file_names: list[str] = []
            for m in commit.modified_files:
                if m.filename:
                    file_names.append(m.filename)
                    entry["files"].add(m.filename)

                # Per-(commit, file) authorship event — substrate for forensics.
                event = attribution.effort_event_from_modified_file(commit, m)
                if event is not None:
                    events.append(event)

            date_str = commit.author_date.strftime("%Y-%m-%d")
            timeline.append({
                "date": date_str,
                "timestamp": commit.author_date.isoformat(),
                "author": author_name,
                "insertions": commit.insertions,
                "deletions": commit.deletions,
                "msg": (commit.msg[:50] + "…") if len(commit.msg) > 50 else commit.msg,
                "files": file_names,
            })

        # Ownership + quality pass — a single git-blame pass over source files,
        # run while the clone still exists on disk.
        if repo_dir and os.path.isdir(repo_dir):
            try:
                stage("attribution")
                source_files = attribution.list_source_files(repo_dir)
                line_ownership = attribution.build_line_ownership(repo_dir, source_files)
                ownership_records = attribution.ownership_from_line_map(line_ownership)
                stage("quality")
                quality_acc_by_email = quality.attribute_quality(repo_dir, line_ownership)
                # Ownership confidence intervals, computed on a canonical-name
                # remap so they align with the merged per-author records.
                stage("ownership_modeling")
                canonical_line_ownership = {
                    path: {ln: email_to_canonical.get(em, em) for ln, em in lines.items()}
                    for path, lines in line_ownership.items()
                }
                ownership_iv = uncertainty.ownership_intervals(canonical_line_ownership)
            except Exception:
                logger.warning("Ownership/quality pass failed for %s", repo_url, exc_info=True)

    except GitCommandError as exc:
        stderr = (getattr(exc, "stderr", "") or str(exc)).lower()
        if "could not create work tree dir" in stderr and "permission denied" in stderr:
            raise RuntimeError(
                "Cannot clone repository due to folder permission issues. "
                "Set the GITSIGHT_CLONE_DIR environment variable to a writable path."
            ) from exc
        if "failed to connect" in stderr or "could not resolve host" in stderr:
            raise RuntimeError(
                "Cannot reach GitHub. Check your internet or firewall settings."
            ) from exc
        if "repository not found" in stderr or "authentication failed" in stderr:
            raise RuntimeError(
                "Repository not accessible. Ensure the URL is correct and the repository is public."
            ) from exc
        raise RuntimeError("Git operation failed while analysing the repository.") from exc

    finally:
        # Always clean up the clone to prevent unbounded disk growth
        if repo_dir and os.path.isdir(repo_dir):
            _safe_rmtree(repo_dir)

    # Merge authors who share an email address
    merged_stats = _merge_author_by_email(stats, email_to_canonical)

    # Build per-email attribution profile (ownership + effort), then attach it to
    # each canonical author by summing across all of that person's emails.
    stage("integrity")
    effort_agg = attribution.aggregate_effort(events)
    profile_by_email = attribution.combine(ownership_records, effort_agg)
    integrity_by_email = integrity.analyze(events, commit_messages, deadline=deadline)

    canonical_emails: dict[str, set[str]] = {}
    for name, data in stats.items():
        email = data.get("_email", "")
        canonical = email_to_canonical.get(email, name)
        canonical_emails.setdefault(canonical, set()).add(email)

    for canonical, info in merged_stats.items():
        agg = {
            "owned_lines": 0, "owned_files": 0,
            "effort_added": 0, "effort_deleted": 0, "effort_commits": 0,
            "ownership_pct": 0.0, "effort_pct": 0.0,
        }
        quality_acc = quality.empty_acc()
        integrity_flags: list[dict] = []
        for em in canonical_emails.get(canonical, set()):
            prof = profile_by_email.get(em)
            if prof:
                for key in agg:
                    agg[key] += prof[key]
            if em in quality_acc_by_email:
                quality.merge_acc(quality_acc, quality_acc_by_email[em])
            integrity_flags.extend(integrity_by_email.get(em, []))
        agg["ownership_pct"] = round(agg["ownership_pct"], 2)
        agg["effort_pct"] = round(agg["effort_pct"], 2)
        agg["divergence"] = round(agg["effort_pct"] - agg["ownership_pct"], 2)
        # Ownership confidence interval (cluster bootstrap over files).
        agg["interval"] = ownership_iv.get(canonical)
        info["attribution"] = agg
        info["quality"] = quality.finalize_quality(quality_acc)
        info["integrity_flags"] = integrity_flags

    # Finalise per-author data
    for info in merged_stats.values():
        info["files"] = list(info["files"])
        # avg_quality keeps backward-compatibility; None when not assessed.
        info["avg_quality"] = info["quality"]["quality_score"]
        info.pop("_email", None)

    return {
        "stats": merged_stats,
        "timeline": timeline,
        "total_commits": commit_count,
        "truncated": truncated,
        "reliability": reliability.assess(commit_meta).as_dict(),
    }
