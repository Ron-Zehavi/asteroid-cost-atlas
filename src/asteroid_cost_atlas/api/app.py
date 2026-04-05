"""FastAPI application for the Asteroid Cost Atlas."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from asteroid_cost_atlas.api.deps import create_db
from asteroid_cost_atlas.api.routes import asteroids, search, stats

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


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

app.state.limiter = limiter

# CORS: restrict origins, configurable via CORS_ORIGINS env var
_default_origins = "http://localhost:5173,http://localhost:8000"
_origins = os.environ.get("CORS_ORIGINS", _default_origins).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return 429 when rate limit is exceeded."""
    return Response(
        content='{"detail": "Rate limit exceeded"}',
        status_code=429,
        media_type="application/json",
    )


@app.middleware("http")
async def security_headers(request: Request, call_next: object) -> Response:
    """Add security headers to all responses."""
    response: Response = await call_next(request)  # type: ignore[operator]
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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
