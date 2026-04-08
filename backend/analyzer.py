import tempfile
import os
import shutil
from pydriller import Repository
from datetime import datetime
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

def calculate_quality(source_code: str) -> dict:
    if not source_code or not source_code.strip():
        return {"overall": 100.0}

    # 1. Cyclomatic Complexity & Readability
    try:
        liz = lizard.analyze_file.analyze_source_code("temp.py", source_code)
        cc = liz.average_cyclomatic_complexity if liz.average_cyclomatic_complexity > 0 else 1
    except:
        cc = 1

    # 2. Maintainability Index
    try:
        mi = radon.metrics.mi_visit(source_code, True)
    except:
        mi = 100.0
        
    # 3. Comment Density
    lines = source_code.splitlines()
    total_lines = len(lines)
    if total_lines == 0:
        cd_score = 100.0
    else:
        comment_lines = sum(1 for line in lines if line.strip().startswith('#') or line.strip().startswith('//') or line.strip().startswith('/*') or line.strip().startswith('*'))
        cd_ratio = comment_lines / total_lines
        cd_score = min(100.0, (cd_ratio / 0.15) * 100.0)

    # 4. Linter Score (approximate via static structural checks instead of full flake8 to preserve in-memory speed over 1000s of files)
    long_lines = sum(1 for line in lines if len(line) > 100)
    linter_score = max(0.0, 100.0 - (long_lines / (total_lines or 1)) * 200.0)
    
    # 5. Readability Score
    avg_len = sum(len(line) for line in lines) / (total_lines or 1)
    readability = max(0.0, 100.0 - max(0, avg_len - 60))
    
    # Normalize CC to 100 scale before formula
    cc_score = (1 / cc) * 100
    
    # User's formula
    overall = (cc_score * 0.35) + (mi * 0.25) + (cd_score * 0.15) + (linter_score * 0.15) + (readability * 0.10)
    
    return {
        "overall": overall
    }

def analyze_repository(repo_url: str):
    """
    Analyzes a given git repository URL and returns contribution statistics.
    Returns a dictionary of author stats and the timeline of commits.
    """
    stats = {}
    timeline = []
    
    print(f"Starting analysis for: {repo_url}")
    try:
        commit_count = 0
        for commit in Repository(repo_url).traverse_commits():
            commit_count += 1
            if commit_count > 1000: # safety limit
                break
                
            author_name = commit.author.name
            
            if author_name not in stats:
                stats[author_name] = {
                    "commits": 0,
                    "lines_added": 0,
                    "lines_deleted": 0,
                    "files_modified": 0,
                    "files": set(),
                    "quality_scores": []
                }
                
            stats[author_name]["commits"] += 1
            stats[author_name]["lines_added"] += commit.insertions
            stats[author_name]["lines_deleted"] += commit.deletions
            stats[author_name]["files_modified"] += commit.files
            
            file_names = []
            for m in commit.modified_files:
                if m.filename:
                    file_names.append(m.filename)
                    if author_name in stats:
                        stats[author_name]["files"].add(m.filename)
                
                # We analyze quality for supported parseable types
                if m.source_code and m.filename and m.filename.endswith(('.py', '.js', '.ts', '.html', '.css', '.java', '.cpp', '.c', '.go')):
                    qs = calculate_quality(m.source_code)
                    stats[author_name]["quality_scores"].append(qs["overall"])
            
            date_str = commit.author_date.strftime("%Y-%m-%d")
            timeline.append({
                "date": date_str,
                "author": author_name,
                "insertions": commit.insertions,
                "deletions": commit.deletions,
                "msg": commit.msg[:50] + "..." if len(commit.msg) > 50 else commit.msg,
                "files": file_names
            })
            
    except Exception as e:
        print(f"Error analyzing repo: {e}")
        raise e
        
    for author, info in stats.items():
        info["files"] = list(info["files"])
        if info["quality_scores"]:
            info["avg_quality"] = sum(info["quality_scores"]) / len(info["quality_scores"])
        else:
            info["avg_quality"] = 100.0 # Default if no decypherable code
        del info["quality_scores"]
        
    return {
        "stats": stats,
        "timeline": timeline,
        "total_commits": commit_count
    }
