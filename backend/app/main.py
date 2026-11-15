"""ScoutForge FastAPI application entrypoint.

Bootstraps the SQLite schema, seeds sample data when the database is empty,
registers all API routers, serves the vanilla-JS dashboard, and exposes a
health check. Run with::

    uvicorn app.main:app --reload

from the ``backend/`` directory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.database import init_db
from app.routers import analytics, candidates, jobs, pipeline, scoring
from app.seed import seed_if_empty

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialise the schema and seed demo data on startup."""
    init_db()
    if seed_if_empty():
        print("[ScoutForge] Seeded sample jobs and candidates.")
    yield


app = FastAPI(
    title="ScoutForge",
    version="1.0.0",
    description=(
        "AI talent acquisition & candidate-sourcing platform: post jobs, "
        "source & score candidates, and run hiring funnels with deterministic "
        "AI shortlisting."
    ),
    lifespan=lifespan,
)


# ── API routers ──────────────────────────────────────────────────────────────
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(pipeline.router)
app.include_router(scoring.router)
app.include_router(analytics.router)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["system"])
def health() -> dict:
    """Liveness probe for load balancers and uptime checks."""
    return {"status": "ok", "service": "ScoutForge", "version": app.version}


# ── Static dashboard (no build step, served directly by FastAPI) ─────────────
@app.get("/", include_in_schema=False)
def _index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def _app_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js")


@app.get("/style.css", include_in_schema=False)
def _style_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "style.css")