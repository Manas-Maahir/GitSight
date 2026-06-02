# GitSight

<img width="1280" height="591" alt="image" src="https://github.com/user-attachments/assets/50f13983-9209-4849-ba8f-3a4ac3d8f2c1" />

**Understand who actually contributed — beyond raw commit counts.**

GitSight analyzes any public GitHub repository’s commit history to produce a fair, multi-factor breakdown of every contributor’s impact, code quality, and integrity. Designed for educators, team leads, and open-source maintainers who need transparent, evidence-backed contribution analysis.

> **Academic Integrity Edition**: GitSight is now focused on **contribution verification and plagiarism detection** for educational contexts. It surfaces ownership confidence intervals, calibrated attribution regimes (cold-start vs trained), integrity signals (commits, diff patterns, authorship forensics), and per-contribution explanations so instructors can verify claims and spot anomalies.

---

## Features

- **Ownership Analysis** — per-author contribution ownership with 90% confidence intervals (not false precision)
- **Role Classification** — Major Contributor, Minor Contributor, or Free Rider based on impact and effort
- **Code Quality Assessment** — per-author average of cyclomatic complexity, maintainability index, comment density, and readability
- **Integrity Forensics** — detects suspicious patterns (mass deletions, unusual commit timing, same-day bulk commits)
- **Calibrated Confidence** — shows whether the system is cold-start (trained on no feedback) or calibrated (trained on instructor reviews)
- **Real-Time Progress** — transparent staged pipeline showing live analysis progress (cloning, parsing history, attribution, quality scoring, etc.)
- **Interactive Dashboard** — linked charts and tables, sortable contributor cards with progressive disclosure, expandable evidence chains
- **Author Deduplication** — merges the same person’s commits across different git display names using email identity

---

## Quick Start

### Run from Docker (recommended)

```bash
docker compose up
# Opens http://127.0.0.1:8000
```

### Run locally (development)

**Backend:**
```bash
cd backend

# 1. Create a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
python main.py
# Server listens on http://127.0.0.1:8000
```

**Frontend (optional, for local development):**
```bash
cd frontend
npm install
npm run dev
# Dev server on http://127.0.0.1:5173 (proxies /api to backend on :8000)
# Production bundle already built into backend/static/
```

---

## How to Use

1. **Open** http://127.0.0.1:8000 in your browser
2. **Paste** a public GitHub repository URL (e.g., `https://github.com/pallets/flask`)
3. **Analyze** — click "Analyse" and watch the live **staged pipeline**:
   - ✓ Cloning repository
   - ⟳ Parsing git history (shows commits parsed, progress %)
   - → Attribution analysis
   - → Code quality
   - → Ownership modeling
   - → Integrity forensics
   - → Scoring contributions
   - → Generating explanations
4. **Review** the dashboard:
   - **Summary header** — repo stats, reliability band, at-a-glance verdict
   - **Trust banner** — reliability factors + calibration regime (cold-start vs calibrated)
   - **Impact chart** — interactive donut showing contribution distribution
   - **Ownership vs Effort** — bar chart showing divergence (who owns vs who churned)
   - **Contributor cards** — sortable table with role, ownership%, effort, quality, integrity flags
<img width="1034" height="586" alt="image" src="https://github.com/user-attachments/assets/9fb92ce9-39f6-43ed-a32f-92e1e46cd667" />

6. **Expand** any contributor card to see:
   - Why this verdict (confidence, caveats, regime)
   - Attribution metrics (ownership, effort, divergence, quality)
   - Integrity signals with expandable evidence chains (commit SHAs)
   - Files modified
   - Commit history timeline
   - **Instructor review** — confirm or correct the role classification
     <img width="741" height="538" alt="image" src="https://github.com/user-attachments/assets/5a481159-f128-44b0-a1ba-0ba174af6dcd" />

7. **Export** as CSV for your records
  
<img width="1354" height="755" alt="image" src="https://github.com/user-attachments/assets/084afcad-293e-4ac3-9053-bc53a27e02d8" />


### Key Features on the Dashboard

- **Theme toggle** — light/dark/system preference (top right)
- **Sortable columns** — click column headers to sort by Impact, Ownership, Effort, Quality, or Integrity Flags
- **Chart linking** — hover a slice in the Impact chart to highlight the corresponding row
- **Confidence intervals** — ownership is shown as a range (e.g. "~67% (40–86%)") — the interval shows uncertainty
- **Calibration regime** — indicates whether confidence bounds are cold-start (untrained) or calibrated (trained on instructor feedback)
- **Integrity evidence** — click "Integrity signals" to expand commit-level evidence; all signals are **advisory** and do not change the role score
- **Instructor review** — select the correct role if the system got it wrong; this trains the confidence model

---

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `GITSIGHT_HOST` | `127.0.0.1` | Server bind address |
| `GITSIGHT_PORT` | `8000` | Server port |
| `GITSIGHT_CLONE_DIR` | `backend/.cache/repo_clones` | Temporary clone directory |
| `GITSIGHT_ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins (set explicitly in production) |
| `GITSIGHT_CACHE_ENABLED` | `true` | Cache analysis results by (repo, HEAD sha) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Analysis** | PyDriller (git), Radon (complexity), Lizard (metrics) |
| **Confidence** | TanStack Query for real-time job polling, sklearn calibration curves |
| **Frontend** | Vite + React 18 + TypeScript, Tailwind CSS v3 (tokens), shadcn/ui (Radix), Framer Motion, Recharts |
| **Storage** | SQLite (analysis cache, instructor reviews) |
| **Deployment** | Docker multi-stage build (Node + Python) |

---

## API

### Async Analysis (recommended)

```bash
# Start a job
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d ‘{"url": "https://github.com/owner/repo"}’
# → { "job_id": "abc123...", "status": "pending" }

# Poll for result
curl http://127.0.0.1:8000/api/jobs/abc123...
# → { "job_id": "abc123", "status": "running", "stage": "parsing_history", "stage_index": 1, ... }
# → (final) { "job_id": "abc123", "status": "done", "result": { "authors": [...], ... } }

# Instructor Review
curl -X POST http://127.0.0.1:8000/api/review \
  -H "Content-Type: application/json" \
  -d ‘{
    "analysis_id": 42,
    "author": "alice",
    "instructor_role": "Major",
    "reviewer": "prof@example.edu",
    "note": "Confirmed; she led the redesign"
  }’
```

### Health & Calibration

```bash
GET /health
→ { "status": "ok", "version": "1.1.0" }

GET /api/calibration?analysis_id=42
→ { "regime": "cold-start", "n_reviews": 5, "ece": 0.12, ... }

POST /api/calibration/train
→ { "regime": "calibrated", "n": 50, "ece": 0.08 }
```

Full API reference: [ARCHITECTURE.md](ARCHITECTURE.md)
