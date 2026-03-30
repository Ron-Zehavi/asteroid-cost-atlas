"""
Data enrichment stage: fills gaps in sparse physical measurements.

Reads the latest sbdb_clean_*.parquet and applies two enrichment layers:

1. **LCDB merge** — joins rotation periods, albedo, and taxonomy from
   the LCDB (Asteroid Lightcurve Database) for objects that lack SBDB
   rotation data.  Only periods with quality U >= 2- are used.

2. **H→diameter estimation** — for objects without a measured diameter,
   computes an estimate from absolute magnitude H:

       D = (1329 / sqrt(p_v)) × 10^(-H/5)

   Uses measured albedo when available (including LCDB-sourced albedo),
   otherwise falls back to DEFAULT_ALBEDO = 0.154.

Output columns added:
  - ``diameter_estimated_km`` — measured or H-derived diameter
  - ``diameter_source``       — "measured" | "estimated" | NaN
  - ``rotation_source``       — "sbdb" | "lcdb" | NaN
  - ``taxonomy``              — LCDB taxonomic class (sparse)

The original ``diameter_km`` and ``rotation_hours`` columns are never
overwritten — provenance columns track the source of every value.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Default geometric albedo when no measurement is available.
# 0.154 is the population-average across all asteroid classes.
DEFAULT_ALBEDO = 0.154

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scalar helper
# ---------------------------------------------------------------------------


def h_to_diameter_km(h: float, albedo: float = DEFAULT_ALBEDO) -> float:
    """
    Convert absolute magnitude H to estimated diameter in km.

    Uses the IAU standard relation:
        D = (1329 / sqrt(albedo)) × 10^(-H/5)

    Returns nan for non-finite inputs or non-positive albedo.
    """
    if not math.isfinite(h) or albedo <= 0 or not math.isfinite(albedo):
        return float("nan")
    result: float = (1329.0 / math.sqrt(albedo)) * 10.0 ** (-h / 5.0)
    return result


# ---------------------------------------------------------------------------
# LCDB merge
# ---------------------------------------------------------------------------


def _latest_lcdb_parquet(raw_dir: Path) -> Path | None:
    """Return the latest lcdb_*.parquet, or None if not yet ingested."""
    candidates = sorted(raw_dir.glob("lcdb_*.parquet"))
    return candidates[-1] if candidates else None


def merge_lcdb(df: pd.DataFrame, lcdb_path: Path) -> pd.DataFrame:
    """
    Merge LCDB rotation periods, albedo, and taxonomy into the catalog.

    - Fills ``rotation_hours`` gaps with LCDB periods (U >= 2-)
    - Fills ``albedo`` gaps with LCDB albedo
    - Adds ``taxonomy`` column from LCDB classification
    - Adds ``rotation_source`` column ("sbdb" | "lcdb" | NaN)

    Join is on ``spkid`` (numbered asteroids only).
    SBDB values are always preferred — LCDB only fills gaps.
    """
    lcdb = pd.read_parquet(lcdb_path)
    logger.info("Loaded %d LCDB records from %s", len(lcdb), lcdb_path.name)

    result = df.copy()
    result["rotation_source"] = pd.array([pd.NA] * len(df), dtype="string")

    # Mark existing SBDB rotation data
    has_sbdb_rot = result["rotation_hours"].notna()
    result.loc[has_sbdb_rot, "rotation_source"] = "sbdb"

    # Merge LCDB on spkid
    lcdb_subset = lcdb[["spkid", "lcdb_rotation_hours", "lcdb_albedo", "taxonomy"]].copy()
    merged = result.merge(lcdb_subset, on="spkid", how="left")

    # Fill rotation gaps
    needs_rot = merged["rotation_hours"].isna() & merged["lcdb_rotation_hours"].notna()
    merged.loc[needs_rot, "rotation_hours"] = merged.loc[needs_rot, "lcdb_rotation_hours"]
    merged.loc[needs_rot, "rotation_source"] = "lcdb"

    # Fill albedo gaps
    if "albedo" in merged.columns:
        needs_albedo = merged["albedo"].isna() & merged["lcdb_albedo"].notna()
        merged.loc[needs_albedo, "albedo"] = merged.loc[needs_albedo, "lcdb_albedo"]

    # Keep taxonomy column, drop LCDB working columns
    merged = merged.drop(columns=["lcdb_rotation_hours", "lcdb_albedo"])

    rot_filled = int(needs_rot.sum())
    logger.info(
        "LCDB merge: %d rotation gaps filled, %d already had SBDB rotation",
        rot_filled,
        int(has_sbdb_rot.sum()),
    )

    return merged


# ---------------------------------------------------------------------------
# H → diameter estimation
# ---------------------------------------------------------------------------


def add_diameter_estimate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ``diameter_estimated_km`` and ``diameter_source`` columns.

    Required input columns: abs_magnitude (H).
    Optional input columns: diameter_km, albedo.

    - Rows with a measured diameter_km get source = "measured" and
      diameter_estimated_km = diameter_km (pass-through).
    - Rows with H but no measured diameter get an estimate from the
      H-to-diameter formula, using measured albedo if available or
      DEFAULT_ALBEDO otherwise.  Source = "estimated".
    - Rows missing both H and diameter get NaN / NaN.
    """
    if "abs_magnitude" not in df.columns:
        raise ValueError("DataFrame is missing required column: abs_magnitude")

    result = df.copy()
    result["diameter_estimated_km"] = np.nan
    result["diameter_source"] = pd.array([pd.NA] * len(df), dtype="string")

    # Pass through measured diameters
    if "diameter_km" in df.columns:
        has_measured = df["diameter_km"].notna()
        result.loc[has_measured, "diameter_estimated_km"] = df.loc[has_measured, "diameter_km"]
        result.loc[has_measured, "diameter_source"] = "measured"
    else:
        has_measured = pd.Series(False, index=df.index)

    # Estimate from H for rows that lack measured diameter but have H
    has_h = df["abs_magnitude"].notna()
    needs_estimate = has_h & ~has_measured

    if needs_estimate.any():
        h = df.loc[needs_estimate, "abs_magnitude"].to_numpy(dtype=float)

        # Use measured albedo where available, else default
        if "albedo" in df.columns:
            a_raw = df.loc[needs_estimate, "albedo"].to_numpy(dtype=float)
            albedo = np.where(np.isfinite(a_raw) & (a_raw > 0), a_raw, DEFAULT_ALBEDO)
        else:
            albedo = np.full_like(h, DEFAULT_ALBEDO)

        valid = np.isfinite(h)
        estimated = np.full_like(h, np.nan)
        estimated[valid] = (1329.0 / np.sqrt(albedo[valid])) * 10.0 ** (-h[valid] / 5.0)

        result.loc[needs_estimate, "diameter_estimated_km"] = estimated
        valid_idx = df.loc[needs_estimate].index[valid]
        result.loc[valid_idx, "diameter_source"] = "estimated"

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _latest_clean_parquet(processed_dir: Path) -> Path:
    candidates = sorted(processed_dir.glob("sbdb_clean_*.parquet"))
    if not candidates:
        raise FileNotFoundError(
            f"No sbdb_clean_*.parquet found in {processed_dir}. "
            "Run 'make clean-data' first."
        )
    return candidates[-1]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists())
    raw_dir = repo_root / "data" / "raw"
    processed_dir = repo_root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    input_path = _latest_clean_parquet(processed_dir)
    logger.info("Reading %s", input_path.name)

    df = pd.read_parquet(input_path)
    logger.info("Loaded %d rows", len(df))

    # Layer 1: LCDB merge (if available)
    lcdb_path = _latest_lcdb_parquet(raw_dir)
    if lcdb_path is not None:
        df = merge_lcdb(df, lcdb_path)
    else:
        logger.info("No LCDB parquet found — skipping rotation enrichment")
        df["rotation_source"] = pd.array([pd.NA] * len(df), dtype="string")
        has_sbdb = df["rotation_hours"].notna()
        df.loc[has_sbdb, "rotation_source"] = "sbdb"
        if "taxonomy" not in df.columns:
            df["taxonomy"] = pd.NA

    # Layer 2: H→diameter estimation (uses LCDB-enriched albedo if available)
    result = add_diameter_estimate(df)

    measured = (result["diameter_source"] == "measured").sum()
    estimated = (result["diameter_source"] == "estimated").sum()
    missing = result["diameter_source"].isna().sum()
    rot_sbdb = (result["rotation_source"] == "sbdb").sum()
    rot_lcdb = (result["rotation_source"] == "lcdb").sum()

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_enriched_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — diameter: %d measured / %d estimated / %d missing | "
        "rotation: %d sbdb / %d lcdb | %.1fs",
        output_path.name,
        measured, estimated, missing,
        rot_sbdb, rot_lcdb,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
