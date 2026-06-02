# --- Frontend build stage -------------------------------------------------
# Builds the Vite/React bundle and emits it into /app/backend/static
# (vite.config.ts: build.outDir = ../backend/static).
FROM node:22-slim AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# --- Python runtime -------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install git (required by PyDriller for cloning)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/ .

# Overlay the freshly built frontend bundle (replaces any committed copy)
COPY --from=frontend /app/backend/static ./static

# Non-root user for security
RUN useradd -m -u 1001 gitsight && \
    mkdir -p /app/.cache/repo_clones && \
    chown -R gitsight:gitsight /app
USER gitsight

ENV GITSIGHT_HOST=0.0.0.0
ENV GITSIGHT_PORT=8000
ENV GITSIGHT_CLONE_DIR=/app/.cache/repo_clones

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
