"""Stats and chart endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from asteroid_cost_atlas.api.deps import db_sql, get_db
from asteroid_cost_atlas.utils.query import CostAtlasDB

router = APIRouter(prefix="/api", tags=["stats"])


def _build_where(
    neo: str | None,
    is_viable: bool | None,
    composition_class: str | None,
    dv_max: float | None,
) -> tuple[str, list[object]]:
    """Build a WHERE clause with parameterized values."""
    clauses: list[str] = []
    params: list[object] = []
    if neo and neo.upper() in ("Y", "N"):
        clauses.append("neo = ?")
        params.append(neo.upper())
    if is_viable is not None:
        clauses.append("is_viable = ?")
        params.append(is_viable)
    if composition_class and composition_class in ("C", "S", "M", "V", "U"):
        clauses.append("composition_class = ?")
        params.append(composition_class)
    if dv_max is not None and dv_max > 0:
        clauses.append("delta_v_km_s <= ?")
        params.append(dv_max)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where, params


@router.get("/stats")
def stats(
    neo: str | None = Query(None),
    is_viable: bool | None = Query(None),
    composition_class: str | None = Query(None),
    dv_max: float | None = Query(None, ge=0),
    db: CostAtlasDB = Depends(get_db),
) -> dict[str, object]:
    """Dashboard summary statistics, optionally filtered."""
    where, params = _build_where(neo, is_viable, composition_class, dv_max)
    rows = db_sql(db, f"""
        SELECT
            COUNT(*)                                        AS total_objects,
            COUNT(delta_v_km_s)                            AS scored_objects,
            COUNT(*) FILTER (
                WHERE tisserand_jupiter >= 2
                AND   tisserand_jupiter  < 3
            )                                              AS nea_candidates,
            ROUND(MIN(delta_v_km_s),    2)                 AS min_delta_v,
            ROUND(MAX(delta_v_km_s),    2)                 AS max_delta_v,
            ROUND(MEDIAN(delta_v_km_s), 2)                 AS median_delta_v,
            ROUND(AVG(delta_v_km_s),    2)                 AS avg_delta_v
        FROM atlas
        {where}
    """, params or None)
    return rows[0] if rows else {}


@router.get("/charts/delta-v")
def delta_v_histogram(
    bin_width: float = Query(1.0, gt=0),
    db: CostAtlasDB = Depends(get_db),
) -> list[dict[str, object]]:
    """Delta-v distribution histogram."""
    return db.delta_v_histogram(  # type: ignore[return-value]
        bin_width=bin_width,
    ).to_dict(orient="records")


@router.get("/charts/composition")
def composition_distribution(
    db: CostAtlasDB = Depends(get_db),
) -> list[dict[str, object]]:
    """Asteroid count by composition class."""
    return db_sql(db, """
        SELECT
            composition_class AS class,
            COUNT(*) AS count,
            COUNTIF(is_viable) AS viable,
            ROUND(SUM(CASE WHEN is_viable
                THEN campaign_profit_usd ELSE 0 END), 0) AS total_profit
        FROM atlas
        WHERE composition_class IS NOT NULL
        GROUP BY composition_class
        ORDER BY count DESC
    """)
