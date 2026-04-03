"""FastAPI application for the Asteroid Cost Atlas."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from asteroid_cost_atlas.api.deps import create_db
from asteroid_cost_atlas.api.routes import asteroids, search, stats

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage CostAtlasDB lifecycle."""
    logger.info("Loading atlas into DuckDB...")
    app.state.db = create_db()
    logger.info("Atlas loaded — ready to serve requests")
    yield
    app.state.db.close()
    logger.info("DuckDB connection closed")


app = FastAPI(
    title="Asteroid Cost Atlas",
    description="Economic accessibility atlas for asteroid mining targets",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


app.include_router(asteroids.router)
app.include_router(stats.router)
app.include_router(search.router)

# Serve built React frontend if it exists (must be last — catches all unmatched routes)
_web_dist = Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist"
if _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="static")
