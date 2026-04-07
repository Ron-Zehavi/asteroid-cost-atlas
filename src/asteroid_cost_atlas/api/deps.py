"""FastAPI dependency injection for the CostAtlasDB query layer."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import Request

from asteroid_cost_atlas.utils.query import CostAtlasDB

_lock = threading.Lock()


def _resolve_processed_dir() -> Path:
    """Resolve the processed data directory.

    Priority: ASTEROID_PROCESSED_DIR env var > repo root (dev) > /app/data/processed (container).
    """
    env_dir = os.environ.get("ASTEROID_PROCESSED_DIR")
    if env_dir:
        return Path(env_dir)
    module = Path(__file__).resolve()
    for p in [module, *module.parents]:
        if (p / "pyproject.toml").exists():
            return p / "data" / "processed"
    return Path("/app/data/processed")


def create_db() -> CostAtlasDB:
    """Create a CostAtlasDB instance from the latest atlas parquet."""
    return CostAtlasDB.from_processed_dir(_resolve_processed_dir())


def get_db(request: Request) -> CostAtlasDB:
    """FastAPI dependency that returns the shared CostAtlasDB instance."""
    return request.app.state.db  # type: ignore[no-any-return]


def db_sql(
    db: CostAtlasDB, query: str, params: list[object] | None = None,
) -> list[dict[str, object]]:
    """Thread-safe SQL execution returning list of dicts."""
    with _lock:
        if params:
            rows = db._conn.execute(query, params).fetchdf().to_dict(orient="records")
        else:
            rows = db.sql(query).to_dict(orient="records")
        return rows  # type: ignore[return-value]
