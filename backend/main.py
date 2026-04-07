from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uvicorn

from analyzer import analyze_repository
from scoring import calculate_scores

app = FastAPI(title="GitHub Contribution Analyzer API")

class RepoRequest(BaseModel):
    url: str

@app.post("/api/analyze")
def analyze_repo(req: RepoRequest):
    if not req.url or not req.url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
        
    try:
        # Run analysis
        data = analyze_repository(req.url)
        # Calculate scores and roles
        scored_authors = calculate_scores(data["stats"])
        
        return {
            "status": "success",
            "repo": req.url,
            "total_commits": data["total_commits"],
            "authors": scored_authors,
            "timeline": data["timeline"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount the static folder
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Static index.html not found"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
