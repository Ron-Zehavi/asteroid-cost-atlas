"""
DuckDB query layer over the processed Parquet atlas.

Provides a zero-server SQL interface for querying the asteroid catalog
without loading the full dataset into memory. Designed to serve as the
read layer for web backends, notebooks, and ad-hoc analysis.

The view name "atlas" is stable — downstream code (API routes, notebooks)
can reference it directly via .sql().

Usage
-----
    from asteroid_cost_atlas.utils.query import CostAtlasDB

    with CostAtlasDB.from_processed_dir(Path("data/processed")) as db:
        df = db.top_accessible(n=20, max_delta_v=8.0)
        df = db.nea_candidates(n=50)
        df = db.stats()
        df = db.sql("SELECT name, delta_v_km_s FROM atlas ORDER BY 2 LIMIT 5")
"""

from __future__ import annotations

import math
from pathlib import Path

import duckdb
import pandas as pd


def _validate_positive_int(name: str, value: int) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")


def _validate_finite_positive(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive, got {value!r}")


class CostAtlasDB:
    """
    In-memory DuckDB connection over a single Parquet atlas file.

    The Parquet file is registered as a view named ``atlas`` so raw SQL
    queries can reference it by name. All query methods return
    ``pd.DataFrame`` — easy to serialise as JSON in a web response or
    display in a notebook.

    Supports the context manager protocol::

        with CostAtlasDB(path) as db:
            df = db.top_accessible()
    """

    VIEW_NAME = "atlas"

    def __init__(self, parquet_path: Path) -> None:
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")
        self._conn = duckdb.connect()
        self._conn.execute(
            f"CREATE VIEW {self.VIEW_NAME} AS "
            f"SELECT * FROM read_parquet('{parquet_path}')"
        )
        self._parquet_path = parquet_path

    def __enter__(self) -> CostAtlasDB:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @classmethod
    def from_processed_dir(cls, processed_dir: Path) -> CostAtlasDB:
        """
        Initialise from a directory, auto-selecting the latest Parquet.

        Preference order: atlas_*.parquet > sbdb_orbital_*.parquet.
        Raises FileNotFoundError if no matching files are found.
        """
        for pattern in ("atlas_*.parquet", "sbdb_orbital_*.parquet"):
            candidates = sorted(processed_dir.glob(pattern))
            if candidates:
                return cls(candidates[-1])
        raise FileNotFoundError(
            f"No atlas_*.parquet or sbdb_orbital_*.parquet files in {processed_dir}"
        )

    # ------------------------------------------------------------------
    # Raw SQL access
    # ------------------------------------------------------------------

    def sql(self, query: str) -> pd.DataFrame:
        """Execute arbitrary SQL against the atlas view and return a DataFrame."""
        return self._conn.execute(query).df()

    # ------------------------------------------------------------------
    # Pre-built queries (common app / API access patterns)
    # ------------------------------------------------------------------

    def top_accessible(
        self,
        n: int = 50,
        max_delta_v: float | None = None,
        max_inclination: float | None = None,
    ) -> pd.DataFrame:
        """
        Return the n asteroids with the lowest delta-v, optionally filtered.

        Parameters
        ----------
        n               : number of rows to return
        max_delta_v     : upper bound on delta_v_km_s
        max_inclination : upper bound on inclination_deg
        """
        _validate_positive_int("n", n)
        filters = ["delta_v_km_s IS NOT NULL"]
        if max_delta_v is not None:
            _validate_finite_positive("max_delta_v", max_delta_v)
            filters.append(f"delta_v_km_s <= {max_delta_v}")
        if max_inclination is not None:
            _validate_finite_positive("max_inclination", max_inclination)
            filters.append(f"inclination_deg <= {max_inclination}")

        where = " AND ".join(filters)
        return self._conn.execute(f"""
            SELECT *
            FROM   {self.VIEW_NAME}
            WHERE  {where}
            ORDER  BY delta_v_km_s ASC
            LIMIT  {n}
        """).df()

    def nea_candidates(
        self,
        n: int = 50,
        max_delta_v: float | None = None,
    ) -> pd.DataFrame:
        """
        Return NEA-range objects (2 <= T_J < 3), sorted by delta-v.

        These are the primary candidates for low-cost mining missions.
        """
        _validate_positive_int("n", n)
        filters = [
            "tisserand_jupiter >= 2",
            "tisserand_jupiter < 3",
            "delta_v_km_s IS NOT NULL",
        ]
        if max_delta_v is not None:
            _validate_finite_positive("max_delta_v", max_delta_v)
            filters.append(f"delta_v_km_s <= {max_delta_v}")

        where = " AND ".join(filters)
        return self._conn.execute(f"""
            SELECT *
            FROM   {self.VIEW_NAME}
            WHERE  {where}
            ORDER  BY delta_v_km_s ASC
            LIMIT  {n}
        """).df()

    def stats(self) -> pd.DataFrame:
        """
        Return a single-row summary suitable for dashboard header cards.

        Columns: total_objects, scored_objects, nea_candidates,
                 min_delta_v, max_delta_v, median_delta_v, avg_delta_v.
        """
        return self._conn.execute(f"""
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
            FROM {self.VIEW_NAME}
        """).df()

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        self._conn.close()

    def delta_v_histogram(self, bin_width: float = 1.0) -> pd.DataFrame:
        """
        Return a binned delta-v distribution for histogram visualisation.

        Columns: bin_floor_km_s, count.

        Raises ValueError if bin_width is not finite and positive.
        """
        _validate_finite_positive("bin_width", bin_width)
        return self._conn.execute(f"""
            SELECT
                ROUND(FLOOR(delta_v_km_s / {bin_width}) * {bin_width}, 4)
                                      AS bin_floor_km_s,
                COUNT(*)              AS count
            FROM   {self.VIEW_NAME}
            WHERE  delta_v_km_s IS NOT NULL
            GROUP  BY 1
            ORDER  BY 1
        """).df()
