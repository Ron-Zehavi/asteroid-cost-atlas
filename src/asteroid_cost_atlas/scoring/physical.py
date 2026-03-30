"""
Physical feasibility scoring features.

Adds three columns that estimate how practical an asteroid is for
surface operations (landing, sampling, or mining):

  surface_gravity_m_s2  — estimated surface gravity (m/s²)
  rotation_feasibility  — operational spin-rate score in [0, 1]
  regolith_likelihood   — probability-like regolith presence score in [0, 1]

All three require physical measurements (diameter_km, rotation_hours)
that are sparse in SBDB (~30 % coverage). Rows missing either input
receive NaN in the output columns.

Surface gravity model
---------------------
Assumes a spherical body with uniform bulk density:

    g = (2/3) × π × G × ρ × D

where G = 6.674 × 10⁻¹¹ m³ kg⁻¹ s⁻², ρ = 2000 kg m⁻³ (typical
S-type/average), and D is diameter in metres.

Rotation feasibility model
--------------------------
Piecewise linear score penalising operationally difficult spin rates:

    period < 2 h    → 0.0  (spin-barrier; centrifugal > gravity)
    2 h ≤ p ≤ 4 h  → ramp 0 → 1
    4 h ≤ p ≤ 100 h → 1.0  (ideal operating window)
    100 h < p ≤ 500 h → ramp 1 → 0.5  (long thermal cycles)
    p > 500 h        → 0.5  (very slow, still feasible but harder)

The 2-hour spin barrier corresponds to the cohesionless rubble-pile
limit (Pravec & Harris 2000).

Regolith likelihood model
-------------------------
Combines two independent signals:

    size_factor     = clamp((D_km − 0.15) / (1.0 − 0.15), 0, 1)
    rotation_factor = clamp((period_h − 2.0) / (4.0 − 2.0), 0, 1)
    regolith_likelihood = size_factor × rotation_factor

Asteroids smaller than ~150 m are unlikely to retain regolith;
fast rotators (< 2 h) shed loose material regardless of size.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Gravitational constant (m³ kg⁻¹ s⁻²)
_G = 6.674e-11

# Assumed bulk density (kg/m³) — average for stony/carbonaceous asteroids
_RHO_KG_M3 = 2000.0

# Pre-computed coefficient: (2/3) × π × G × ρ
_GRAVITY_COEFF = (2.0 / 3.0) * math.pi * _G * _RHO_KG_M3

_DIAMETER_COLUMN_PRIORITY = ("diameter_estimated_km", "diameter_km")
_ROTATION_COLUMN = "rotation_hours"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def surface_gravity_m_s2(diameter_km: float) -> float:
    """
    Estimated surface gravity in m/s² for a spherical body of given diameter.

    Returns nan for non-positive or non-finite diameter.
    """
    if diameter_km <= 0 or not math.isfinite(diameter_km):
        return float("nan")
    diameter_m = diameter_km * 1000.0
    return _GRAVITY_COEFF * diameter_m


def rotation_feasibility(period_hours: float) -> float:
    """
    Operational feasibility score in [0, 1] based on rotation period.

    Returns nan for non-positive or non-finite period.
    """
    if period_hours <= 0 or not math.isfinite(period_hours):
        return float("nan")
    if period_hours < 2.0:
        return 0.0
    if period_hours <= 4.0:
        return (period_hours - 2.0) / 2.0
    if period_hours <= 100.0:
        return 1.0
    if period_hours <= 500.0:
        return 1.0 - 0.5 * (period_hours - 100.0) / 400.0
    return 0.5


def regolith_likelihood(diameter_km: float, period_hours: float) -> float:
    """
    Regolith presence score in [0, 1].

    Combines a size factor (larger bodies retain regolith) with a
    rotation factor (fast rotators shed loose material).

    Returns nan if either input is non-positive or non-finite.
    """
    if (
        diameter_km <= 0
        or period_hours <= 0
        or not math.isfinite(diameter_km)
        or not math.isfinite(period_hours)
    ):
        return float("nan")
    size_factor = max(0.0, min(1.0, (diameter_km - 0.15) / (1.0 - 0.15)))
    rot_factor = max(0.0, min(1.0, (period_hours - 2.0) / (4.0 - 2.0)))
    return size_factor * rot_factor


# ---------------------------------------------------------------------------
# Vectorised DataFrame transformer
# ---------------------------------------------------------------------------


def _resolve_diameter_column(df: pd.DataFrame) -> str | None:
    """Return the best available diameter column name, or None."""
    for col in _DIAMETER_COLUMN_PRIORITY:
        if col in df.columns:
            return col
    return None


def add_physical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add physical feasibility columns to the asteroid DataFrame.

    Diameter source: uses ``diameter_estimated_km`` if present (from the
    enrichment stage), otherwise falls back to ``diameter_km``.

    Each feature is scored independently where possible:
      - surface_gravity_m_s2  — needs diameter only
      - rotation_feasibility  — needs rotation_hours only
      - regolith_likelihood   — needs both diameter and rotation_hours

    Raises ValueError if neither a diameter column nor rotation_hours
    is found in the DataFrame.
    """
    d_col = _resolve_diameter_column(df)
    has_rot = _ROTATION_COLUMN in df.columns

    if d_col is None and not has_rot:
        raise ValueError(
            "DataFrame must have at least one of "
            f"{_DIAMETER_COLUMN_PRIORITY} or '{_ROTATION_COLUMN}'"
        )

    result = df.copy()
    for col in ("surface_gravity_m_s2", "rotation_feasibility", "regolith_likelihood"):
        result[col] = np.nan

    # --- Surface gravity (diameter only) ---
    if d_col is not None:
        d_notna = df[d_col].notna()
        d_raw = df.loc[d_notna, d_col].to_numpy(dtype=float)
        d_valid = np.isfinite(d_raw) & (d_raw > 0)

        d_mask = d_notna.copy()
        d_mask.loc[d_notna] = d_valid
        result.loc[d_mask, "surface_gravity_m_s2"] = (
            _GRAVITY_COEFF * (d_raw[d_valid] * 1000.0)
        )

    # --- Rotation feasibility (rotation only) ---
    if has_rot:
        p_notna = df[_ROTATION_COLUMN].notna()
        p_raw = df.loc[p_notna, _ROTATION_COLUMN].to_numpy(dtype=float)
        p_valid = np.isfinite(p_raw) & (p_raw > 0)

        p_mask = p_notna.copy()
        p_mask.loc[p_notna] = p_valid
        p = p_raw[p_valid]

        conditions = [
            p < 2.0,
            (p >= 2.0) & (p <= 4.0),
            (p > 4.0) & (p <= 100.0),
            (p > 100.0) & (p <= 500.0),
            p > 500.0,
        ]
        choices = [
            np.zeros_like(p),
            (p - 2.0) / 2.0,
            np.ones_like(p),
            1.0 - 0.5 * (p - 100.0) / 400.0,
            np.full_like(p, 0.5),
        ]
        result.loc[p_mask, "rotation_feasibility"] = np.select(conditions, choices)

    # --- Regolith likelihood (needs both) ---
    if d_col is not None and has_rot:
        both_notna = df[d_col].notna() & df[_ROTATION_COLUMN].notna()
        d_raw2 = df.loc[both_notna, d_col].to_numpy(dtype=float)
        p_raw2 = df.loc[both_notna, _ROTATION_COLUMN].to_numpy(dtype=float)
        both_valid = (
            np.isfinite(d_raw2) & np.isfinite(p_raw2) & (d_raw2 > 0) & (p_raw2 > 0)
        )
        both_mask = both_notna.copy()
        both_mask.loc[both_notna] = both_valid

        d2 = d_raw2[both_valid]
        p2 = p_raw2[both_valid]
        size_factor = np.clip((d2 - 0.15) / (1.0 - 0.15), 0.0, 1.0)
        rot_factor = np.clip((p2 - 2.0) / (4.0 - 2.0), 0.0, 1.0)
        result.loc[both_mask, "regolith_likelihood"] = size_factor * rot_factor

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _latest_orbital_parquet(processed_dir: Path) -> Path:
    candidates = sorted(processed_dir.glob("sbdb_orbital_*.parquet"))
    if not candidates:
        raise FileNotFoundError(
            f"No sbdb_orbital_*.parquet found in {processed_dir}. "
            "Run 'make score-orbital' first."
        )
    return candidates[-1]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists())
    processed_dir = repo_root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    input_path = _latest_orbital_parquet(processed_dir)
    logger.info("Reading %s", input_path.name)

    df = pd.read_parquet(input_path)
    logger.info("Loaded %d rows", len(df))

    result = add_physical_features(df)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_physical_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    scored = result["surface_gravity_m_s2"].notna().sum()
    logger.info(
        "Saved %s — %d rows scored, %d skipped (missing diameter/rotation), %.1fs",
        output_path.name,
        scored,
        len(result) - scored,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
