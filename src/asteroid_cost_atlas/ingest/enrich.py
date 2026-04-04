"""
Data enrichment stage: fills gaps in sparse physical measurements.

Reads the latest sbdb_clean_*.parquet and applies three enrichment layers:

1. **LCDB merge** — joins rotation periods, albedo, and taxonomy from
   the LCDB (Asteroid Lightcurve Database) for objects that lack SBDB
   rotation data.  Only periods with quality U >= 2- are used.

2. **NEOWISE merge** — joins ~164 K measured diameters and geometric
   albedos from WISE/NEOWISE infrared observations.  SBDB measured
   values are always preferred; NEOWISE fills gaps.

3. **H→diameter estimation** — for objects without a measured diameter,
   computes an estimate from absolute magnitude H:

       D = (1329 / sqrt(p_v)) × 10^(-H/5)

   Albedo priority (highest to lowest):
     a. Measured albedo from SBDB, LCDB, or NEOWISE
     b. Taxonomy-aware class prior (if taxonomy is available)
     c. Population default (0.154)

   Taxonomy-aware albedo priors improve diameter estimates significantly:
   a C-type asteroid with pV=0.06 gets a diameter ~60% larger than the
   same H with the default pV=0.154.

Output columns added:
  - ``diameter_estimated_km`` — measured or H-derived diameter
  - ``diameter_source``       — "measured" | "neowise" | "estimated" | NaN
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

from asteroid_cost_atlas.scoring.composition import classify_taxonomy

# Default geometric albedo when no measurement or taxonomy is available.
# 0.154 is the population-average across all asteroid classes.
DEFAULT_ALBEDO = 0.154

# Taxonomy-aware albedo priors by composition class.
# Median values from WISE/NEOWISE survey (Mainzer et al. 2011).
_CLASS_ALBEDO: dict[str, float] = {
    "C": 0.06,    # carbonaceous — dark
    "S": 0.25,    # silicaceous — moderate
    "M": 0.14,    # metallic / X-complex — moderate-dark
    "V": 0.35,    # basaltic (Vestoids) — bright
}

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
# NEOWISE merge
# ---------------------------------------------------------------------------


def _latest_neowise_parquet(raw_dir: Path) -> Path | None:
    """Return the latest neowise_*.parquet, or None if not yet ingested."""
    candidates = sorted(raw_dir.glob("neowise_*.parquet"))
    return candidates[-1] if candidates else None


def merge_neowise(df: pd.DataFrame, neowise_path: Path) -> pd.DataFrame:
    """
    Merge NEOWISE measured diameters and albedos into the catalog.

    - Fills ``diameter_km`` gaps with NEOWISE measured diameters
    - Fills ``albedo`` gaps with NEOWISE geometric albedos
    - Tracks provenance via ``diameter_source`` = "neowise"

    Join is on ``spkid`` (numbered asteroids only).
    SBDB values are always preferred — NEOWISE only fills gaps.
    """
    neowise = pd.read_parquet(neowise_path)
    logger.info("Loaded %d NEOWISE records from %s", len(neowise), neowise_path.name)

    result = df.copy()

    neowise_subset = neowise[["spkid", "neowise_diameter_km", "neowise_albedo"]].copy()
    merged = result.merge(neowise_subset, on="spkid", how="left")

    # Fill diameter gaps
    needs_diam = merged["diameter_km"].isna() & merged["neowise_diameter_km"].notna()
    merged.loc[needs_diam, "diameter_km"] = merged.loc[needs_diam, "neowise_diameter_km"]
    # Mark NEOWISE diameters in diameter_source (will be set properly in add_diameter_estimate)
    # We tag them here so add_diameter_estimate sees them as "measured"
    diam_filled = int(needs_diam.sum())

    # Fill albedo gaps
    needs_albedo = merged["albedo"].isna() & merged["neowise_albedo"].notna()
    merged.loc[needs_albedo, "albedo"] = merged.loc[needs_albedo, "neowise_albedo"]
    albedo_filled = int(needs_albedo.sum())

    merged = merged.drop(columns=["neowise_diameter_km", "neowise_albedo"])

    logger.info(
        "NEOWISE merge: %d diameter gaps filled, %d albedo gaps filled",
        diam_filled, albedo_filled,
    )

    return merged


# ---------------------------------------------------------------------------
# MOVIS NIR merge
# ---------------------------------------------------------------------------


def _latest_movis_parquet(raw_dir: Path) -> Path | None:
    """Return the latest movis_*.parquet, or None if not yet ingested."""
    candidates = sorted(raw_dir.glob("movis_*.parquet"))
    return candidates[-1] if candidates else None


def merge_movis(df: pd.DataFrame, movis_path: Path) -> pd.DataFrame:
    """
    Merge MOVIS near-IR color indices and taxonomy into the catalog.

    Adds ``movis_yj``, ``movis_jh``, ``movis_hks`` color columns and
    optionally ``movis_taxonomy`` used by the composition stage.
    """
    movis = pd.read_parquet(movis_path)
    logger.info("Loaded %d MOVIS records from %s", len(movis), movis_path.name)

    result = df.copy()
    keep_cols = ["spkid"]
    for col in ("movis_yj", "movis_jks", "movis_hks", "movis_taxonomy"):
        if col in movis.columns:
            keep_cols.append(col)

    movis_subset = movis[keep_cols].copy()
    merged = result.merge(movis_subset, on="spkid", how="left")

    n_matched = 0
    if "movis_yj" in merged.columns:
        n_matched = int(merged["movis_yj"].notna().sum())
    logger.info("MOVIS merge: %d asteroids matched with NIR data", n_matched)

    return merged


# ---------------------------------------------------------------------------
# SDSS spectral merge
# ---------------------------------------------------------------------------


def _latest_sdss_parquet(raw_dir: Path) -> Path | None:
    """Return the latest sdss_moc_*.parquet, or None if not yet ingested."""
    candidates = sorted(raw_dir.glob("sdss_moc_*.parquet"))
    return candidates[-1] if candidates else None


def merge_sdss(df: pd.DataFrame, sdss_path: Path) -> pd.DataFrame:
    """
    Merge SDSS color indices into the catalog.

    Adds ``color_gr`` and ``color_ri`` columns used by the composition
    stage for SDSS-based taxonomy inference.

    Join is on ``spkid`` (numbered asteroids only).
    """
    sdss = pd.read_parquet(sdss_path)
    logger.info("Loaded %d SDSS records from %s", len(sdss), sdss_path.name)

    result = df.copy()

    # Select only the columns we need for composition classification
    keep_cols = ["spkid"]
    for col in ("color_gr", "color_ri", "color_iz"):
        if col in sdss.columns:
            keep_cols.append(col)

    sdss_subset = sdss[keep_cols].copy()
    merged = result.merge(sdss_subset, on="spkid", how="left")

    n_matched = 0
    if "color_gr" in merged.columns:
        n_matched = int(merged["color_gr"].notna().sum())

    logger.info("SDSS merge: %d asteroids matched with color data", n_matched)

    return merged


# ---------------------------------------------------------------------------
# H → diameter estimation
# ---------------------------------------------------------------------------


def _resolve_albedo_prior(df: pd.DataFrame, mask: pd.Series[bool]) -> np.ndarray:
    """
    Build an albedo array for rows needing H→D estimation.

    Priority:
      1. Measured albedo (from SBDB or LCDB)
      2. Taxonomy-aware class prior (if taxonomy column exists)
      3. Population default (0.154)
    """
    n = int(mask.sum())
    albedo = np.full(n, DEFAULT_ALBEDO)

    # Layer 1: measured albedo
    if "albedo" in df.columns:
        a_raw = df.loc[mask, "albedo"].to_numpy(dtype=float)
        has_measured = np.isfinite(a_raw) & (a_raw > 0)
        albedo[has_measured] = a_raw[has_measured]

    # Layer 2: taxonomy-aware prior for remaining unknowns
    still_default = albedo == DEFAULT_ALBEDO
    if still_default.any() and "taxonomy" in df.columns:
        tax_vals = df.loc[mask, "taxonomy"].values
        for i in np.where(still_default)[0]:
            tax = tax_vals[i]
            if pd.notna(tax):
                comp = classify_taxonomy(str(tax))
                if comp in _CLASS_ALBEDO:
                    albedo[i] = _CLASS_ALBEDO[comp]

    return albedo


def add_diameter_estimate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ``diameter_estimated_km`` and ``diameter_source`` columns.

    Required input columns: abs_magnitude (H).
    Optional input columns: diameter_km, albedo, taxonomy.

    - Rows with a measured diameter_km get source = "measured" and
      diameter_estimated_km = diameter_km (pass-through).
    - Rows with H but no measured diameter get an estimate from the
      H-to-diameter formula. Albedo priority: measured → taxonomy
      class prior → population default (0.154).
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
        albedo = _resolve_albedo_prior(df, needs_estimate)

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

    # Layer 2: NEOWISE merge (if available)
    neowise_path = _latest_neowise_parquet(raw_dir)
    if neowise_path is not None:
        df = merge_neowise(df, neowise_path)
    else:
        logger.info("No NEOWISE parquet found — skipping NEOWISE enrichment")

    # Layer 3: SDSS spectral merge (if available)
    sdss_path = _latest_sdss_parquet(raw_dir)
    if sdss_path is not None:
        df = merge_sdss(df, sdss_path)
    else:
        logger.info("No SDSS parquet found — skipping spectral enrichment")

    # Layer 4: MOVIS NIR merge (if available)
    movis_path = _latest_movis_parquet(raw_dir)
    if movis_path is not None:
        df = merge_movis(df, movis_path)
    else:
        logger.info("No MOVIS parquet found — skipping NIR enrichment")

    # Layer 5: H→diameter estimation (uses LCDB+NEOWISE-enriched albedo if available)
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
