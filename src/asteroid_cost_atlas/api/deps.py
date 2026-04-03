"""FastAPI dependency injection for the CostAtlasDB query layer."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import Request

from asteroid_cost_atlas.utils.query import CostAtlasDB

_lock = threading.Lock()


def _resolve_processed_dir() -> Path:
    """Resolve the processed data directory from the repo root."""
    module = Path(__file__).resolve()
    repo_root = next(
        p for p in [module, *module.parents] if (p / "pyproject.toml").exists()
    )
    return repo_root / "data" / "processed"


def create_db() -> CostAtlasDB:
    """Create a CostAtlasDB instance from the latest atlas parquet."""
    return CostAtlasDB.from_processed_dir(_resolve_processed_dir())


def get_db(request: Request) -> CostAtlasDB:
    """FastAPI dependency that returns the shared CostAtlasDB instance."""
    return request.app.state.db  # type: ignore[no-any-return]


def db_sql(db: CostAtlasDB, query: str) -> list[dict[str, object]]:
    """Thread-safe SQL execution returning list of dicts."""
    with _lock:
        rows = db.sql(query).to_dict(orient="records")
        return rows  # type: ignore[return-value]
