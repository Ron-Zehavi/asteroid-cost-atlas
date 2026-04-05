"""Asteroid endpoints: list, detail, top accessible, NEA candidates."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from asteroid_cost_atlas.api.deps import db_sql, get_db
from asteroid_cost_atlas.api.schemas import (
    COMPOSITION_CLASSES,
    SORTABLE_COLUMNS,
    AsteroidQuery,
)
from asteroid_cost_atlas.utils.query import CostAtlasDB

router = APIRouter(prefix="/api/asteroids", tags=["asteroids"])

ORBIT_CLASSES = frozenset({
    "AMO", "APO", "ATE", "IEO", "MCA", "IMB", "MBA", "OMB", "TJN",
    "CEN", "TNO", "PAA", "HYA", "JFC", "HTC", "ETc", "CTc", "JFc",
})


@router.get("")
def list_asteroids(
    q: AsteroidQuery = Depends(),
    db: CostAtlasDB = Depends(get_db),
) -> dict[str, object]:
    """Paginated, filterable asteroid list."""
    if q.sort not in SORTABLE_COLUMNS:
        raise HTTPException(400, f"Invalid sort column: {q.sort}")
    if q.order not in ("asc", "desc"):
        raise HTTPException(400, f"Invalid order: {q.order}")
    if q.composition_class and q.composition_class not in COMPOSITION_CLASSES:
        raise HTTPException(400, f"Invalid composition_class: {q.composition_class}")
    if q.orbit_class and q.orbit_class not in ORBIT_CLASSES:
        raise HTTPException(400, f"Invalid orbit_class: {q.orbit_class}")

    clauses: list[str] = []
    params: list[object] = []

    if q.neo is not None:
        val = q.neo.upper()
        if val in ("Y", "N"):
            clauses.append("neo = ?")
            params.append(val)
    if q.is_viable is not None:
        clauses.append("is_viable = ?")
        params.append(q.is_viable)
    if q.composition_class:
        clauses.append("composition_class = ?")
        params.append(q.composition_class)
    if q.orbit_class:
        clauses.append("orbit_class = ?")
        params.append(q.orbit_class)
    if q.dv_min is not None:
        clauses.append("delta_v_km_s >= ?")
        params.append(q.dv_min)
    if q.dv_max is not None:
        clauses.append("delta_v_km_s <= ?")
        params.append(q.dv_max)
    if q.rank_max is not None:
        clauses.append("economic_priority_rank <= ?")
        params.append(q.rank_max)

    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    # Sort column is validated against SORTABLE_COLUMNS whitelist above
    sort_col = q.sort
    sort_dir = "ASC" if q.order == "asc" else "DESC"

    count_sql = f"SELECT COUNT(*) AS total FROM atlas {where}"
    total = db_sql(db, count_sql, params)[0]["total"]

    data_sql = (
        f"SELECT * FROM atlas {where} "
        f"ORDER BY {sort_col} {sort_dir} NULLS LAST "
        f"LIMIT ? OFFSET ?"
    )
    rows = db_sql(db, data_sql, [*params, q.limit, q.offset])

    return {"total": total, "limit": q.limit, "offset": q.offset, "data": rows}


@router.get("/top")
def top_accessible(
    n: int = Query(50, ge=1, le=1000),
    max_delta_v: float | None = Query(None, ge=0),
    max_inclination: float | None = Query(None, ge=0),
    db: CostAtlasDB = Depends(get_db),
) -> list[dict[str, object]]:
    """Most accessible asteroids by delta-v."""
    return db.top_accessible(  # type: ignore[return-value]
        n=n, max_delta_v=max_delta_v, max_inclination=max_inclination,
    ).to_dict(orient="records")


@router.get("/nea")
def nea_candidates(
    n: int = Query(50, ge=1, le=1000),
    max_delta_v: float | None = Query(None, ge=0),
    db: CostAtlasDB = Depends(get_db),
) -> list[dict[str, object]]:
    """NEA candidates (2 <= T_J < 3)."""
    return db.nea_candidates(  # type: ignore[return-value]
        n=n, max_delta_v=max_delta_v,
    ).to_dict(orient="records")


@router.get("/{spkid}")
def get_asteroid(
    spkid: int,
    db: CostAtlasDB = Depends(get_db),
) -> dict[str, object]:
    """Single asteroid by spkid."""
    rows = db_sql(db, "SELECT * FROM atlas WHERE spkid = ?", [spkid])
    if not rows:
        raise HTTPException(404, f"Asteroid {spkid} not found")
    return rows[0]
