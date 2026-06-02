"""
Contribution scoring and role classification.

Two scoring modes:

* **ownership** (used for real analyses) — the impact score is an ownership-primary
  blend of surviving-line ownership, breadth of owned files, and authored effort.
  Surviving ownership dominates because it is the least gameable signal.
* **legacy** (fallback) — the original churn-based blend (commits/lines/files),
  used when attribution data is absent (e.g. callers that build stats by hand).

Integrity flags (populated by the forensics layer) are carried alongside the role,
never silently folded into the number — graders need every penalty to be visible
and appealable.
"""

import config


def _new_entry(author: str, stats: dict, impact: float, **extra) -> dict:
    avg_quality = stats.get("avg_quality")
    entry = {
        "author": author,
        "stats": stats,
        "score": round(impact, 2),
        "quality_score": round(avg_quality, 2) if isinstance(avg_quality, (int, float)) else None,
        "quality": stats.get("quality"),
        "integrity_flags": list(stats.get("integrity_flags", [])),
        "ownership_pct": None,
        "effort_pct": None,
        "divergence": None,
        "ownership_interval": (stats.get("attribution") or {}).get("interval"),
        "boundary_case": False,
        "commit_ratio": None,
        "lines_ratio": None,
    }
    entry.update(extra)
    return entry


def _uses_ownership(stats: dict[str, dict]) -> bool:
    return bool(stats) and all("attribution" in s for s in stats.values())


def _score_ownership(stats: dict[str, dict]) -> list[dict]:
    total_owned_files = sum(s["attribution"]["owned_files"] for s in stats.values())

    scored: list[dict] = []
    for author, s in stats.items():
        attr = s["attribution"]
        ownership_pct = attr["ownership_pct"]
        effort_pct = attr["effort_pct"]
        breadth_pct = (attr["owned_files"] / total_owned_files * 100) if total_owned_files else 0.0

        impact = (
            ownership_pct * config.IMPACT_WEIGHT_OWNERSHIP
            + breadth_pct * config.IMPACT_WEIGHT_BREADTH
            + effort_pct * config.IMPACT_WEIGHT_EFFORT
        )

        scored.append(_new_entry(
            author, s, impact,
            ownership_pct=ownership_pct,
            effort_pct=effort_pct,
            divergence=attr["divergence"],
        ))
    return scored


def _score_legacy(stats: dict[str, dict]) -> list[dict]:
    total_commits = sum(s["commits"] for s in stats.values())
    total_lines = sum(s["lines_added"] + s["lines_deleted"] for s in stats.values())
    total_files = sum(s["files_modified"] for s in stats.values())

    scored: list[dict] = []
    for author, s in stats.items():
        commit_ratio = s["commits"] / total_commits
        lines_ratio = (s["lines_added"] + s["lines_deleted"]) / total_lines
        files_ratio = s["files_modified"] / total_files

        impact = (
            commit_ratio * config.IMPACT_WEIGHT_COMMITS
            + lines_ratio * config.IMPACT_WEIGHT_LINES
            + files_ratio * config.IMPACT_WEIGHT_FILES
        ) * 100

        scored.append(_new_entry(
            author, s, impact,
            commit_ratio=commit_ratio,
            lines_ratio=lines_ratio,
        ))
    return scored


def _assign_roles(scored: list[dict]) -> None:
    num_authors = len(scored)
    expected_avg = 100.0 / num_authors if num_authors > 0 else 0.0
    major_t = expected_avg * config.ROLE_MAJOR_THRESHOLD
    free_t = expected_avg * config.ROLE_FREE_RIDER_THRESHOLD
    margin = config.TRUST_BOUNDARY_MARGIN * expected_avg
    for sa in scored:
        if num_authors == 1 or sa["score"] >= major_t:
            sa["role"] = "Major Contributor"
        elif sa["score"] <= free_t:
            sa["role"] = "Free Rider"
        else:
            sa["role"] = "Minor Contributor"
        # Boundary case: score sits close to a role threshold → verdict is fragile.
        sa["boundary_case"] = num_authors > 1 and (
            abs(sa["score"] - major_t) < margin or abs(sa["score"] - free_t) < margin
        )


def calculate_scores(stats: dict[str, dict]) -> list[dict]:
    if not stats:
        return []

    if _uses_ownership(stats):
        total_signal = sum(
            s["attribution"]["owned_lines"]
            + s["attribution"]["effort_added"]
            + s["attribution"]["effort_deleted"]
            for s in stats.values()
        )
        if total_signal == 0:
            return [_new_entry(a, s, 0.0, role="Minor Contributor") for a, s in stats.items()]
        scored = _score_ownership(stats)
    else:
        total_commits = sum(s["commits"] for s in stats.values())
        total_lines = sum(s["lines_added"] + s["lines_deleted"] for s in stats.values())
        total_files = sum(s["files_modified"] for s in stats.values())
        if total_commits == 0 or total_lines == 0 or total_files == 0:
            return [_new_entry(a, s, 0.0, role="Minor Contributor") for a, s in stats.items()]
        scored = _score_legacy(stats)

    _assign_roles(scored)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
