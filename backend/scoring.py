def calculate_scores(stats: dict):
    if not stats:
        return []

    # Calculate baseline max/averages
    total_commits = sum(s["commits"] for s in stats.values())
    total_lines = sum(s["lines_added"] + s["lines_deleted"] for s in stats.values())
    total_files = sum(s["files_modified"] for s in stats.values())

    if total_commits == 0 or total_lines == 0 or total_files == 0:
        # Edge case: Empty repository or stats
        return [{"author": author, "score": 0, "role": "Minor Contributor"} for author in stats]

    # Calculate a composite impact score for each author (0 to 100 roughly)
    scored_authors = []
    
    for author, s in stats.items():
        # normalize
        commit_ratio = s["commits"] / total_commits
        lines_ratio = (s["lines_added"] + s["lines_deleted"]) / total_lines
        files_ratio = s["files_modified"] / total_files
        
        # weights: 30% commits, 50% lines, 20% files
        impact_score = (commit_ratio * 0.3 + lines_ratio * 0.5 + files_ratio * 0.2) * 100
        
        quality_score = s.get("avg_quality", 100.0)
        
        scored_authors.append({
            "author": author,
            "stats": s,
            "score": round(impact_score, 2),
            "quality_score": round(quality_score, 2),
            "commit_ratio": commit_ratio,
            "lines_ratio": lines_ratio
        })
        
    # Determine Roles
    # Average score if distributed equally would be 100 / num_authors
    num_authors = len(scored_authors)
    expected_average = 100.0 / num_authors if num_authors > 0 else 0
    
    for sa in scored_authors:
        # If someone does more than 1.5x what average would be, Major Contributor
        if sa["score"] >= expected_average * 1.5:
            sa["role"] = "Major Contributor"
        # If someone does less than 0.3x the expected average, Free Rider
        elif sa["score"] <= expected_average * 0.3:
            sa["role"] = "Free Rider"
        else:
            sa["role"] = "Minor Contributor"
            
    # Sort by score descending
    scored_authors.sort(key=lambda x: x["score"], reverse=True)
    return scored_authors
