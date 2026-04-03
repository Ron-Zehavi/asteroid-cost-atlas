"""Search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from asteroid_cost_atlas.api.deps import db_sql, get_db
from asteroid_cost_atlas.utils.query import CostAtlasDB

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    db: CostAtlasDB = Depends(get_db),
) -> list[dict[str, object]]:
    """Search asteroids by name (case-insensitive substring match)."""
    # Sanitize: remove single quotes to prevent SQL injection
    clean_q = q.replace("'", "")
    return db_sql(db, f"""
        SELECT spkid, name, composition_class, orbit_class, neo,
               ROUND(delta_v_km_s, 2) AS delta_v_km_s,
               ROUND(diameter_estimated_km, 3) AS diameter_estimated_km,
               economic_priority_rank, is_viable
        FROM atlas
        WHERE name ILIKE '%{clean_q}%'
        ORDER BY economic_priority_rank ASC NULLS LAST
        LIMIT {limit}
    """)
