import tempfile
import os
import shutil
from pydriller import Repository
from datetime import datetime

def analyze_repository(repo_url: str):
    """
    Analyzes a given git repository URL and returns contribution statistics.
    Returns a dictionary of author stats and the timeline of commits.
    """
    stats = {}
    timeline = []
    
    # We use PyDriller to traverse the commits.
    # To prevent huge repo overhead, we yield or process commits.
    # PyDriller automatically handles remote URLs by cloning to a temp directory.
    
    print(f"Starting analysis for: {repo_url}")
    try:
        # Traverse commits (we'll limit to a reasonable number if it's too large, but for college projects it shouldn't be massive)
        # However, to be safe, we'll track the count.
        commit_count = 0
        for commit in Repository(repo_url).traverse_commits():
            commit_count += 1
            if commit_count > 1000: # safety limit for demo purposes
                break
                
            author_name = commit.author.name
            
            if author_name not in stats:
                stats[author_name] = {
                    "commits": 0,
                    "lines_added": 0,
                    "lines_deleted": 0,
                    "files_modified": 0
                }
                
            stats[author_name]["commits"] += 1
            stats[author_name]["lines_added"] += commit.insertions
            stats[author_name]["lines_deleted"] += commit.deletions
            stats[author_name]["files_modified"] += commit.files
            
            # Simple timeline aggregation (by day)
            date_str = commit.author_date.strftime("%Y-%m-%d")
            timeline.append({
                "date": date_str,
                "author": author_name,
                "insertions": commit.insertions,
                "deletions": commit.deletions,
                "msg": commit.msg[:50] + "..." if len(commit.msg) > 50 else commit.msg
            })
            
    except Exception as e:
        print(f"Error analyzing repo: {e}")
        raise e
        
    return {
        "stats": stats,
        "timeline": timeline,
        "total_commits": commit_count
    }
