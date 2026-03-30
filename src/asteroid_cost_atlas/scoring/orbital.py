"""
Orbital accessibility scoring features.

Adds three proxy columns to the asteroid DataFrame:

  tisserand_jupiter   — Tisserand parameter w.r.t. Jupiter (dimensionless)
  delta_v_km_s        — Simplified mission delta-v estimate (km/s)
  inclination_penalty — Normalised plane-change cost in [0, 1]

These are engineering approximations suitable for ranking and filtering
at catalog scale (~1.5M objects). They are not a substitute for full
trajectory optimisation.

Delta-v model
-------------
Assumes a minimum-energy (Hohmann-like) transfer from a 1 AU circular
orbit (Earth) to a circular orbit at the asteroid's semi-major axis,
plus an out-of-plane correction at the transfer midpoint:

    Δv₁  = v⊕ × |√(2a / (1+a)) − 1|          departure burn
    Δv₂  = (v⊕/√a) × |1 − √(2 / (1+a))|      arrival circularisation
    Δv_i = 2 × v_mid × sin(i/2)               inclination correction
    ΔV   = √(Δv₁² + Δv₂² + Δv_i²)

where v⊕ = 29.78 km/s and v_mid = v⊕ × √(2/(1+a)).

Eccentricity is excluded from the delta-v term (circular-orbit
approximation); it enters only via the Tisserand parameter.

References
----------
Shoemaker & Helin (1979); Sanchez & McInnes (2011) "Asteroid Resource
Map for Near-Earth Space", J. Spacecraft Rockets 48(1).
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

V_EARTH_KM_S: float = 29.78
A_JUPITER_AU: float = 5.2026

_REQUIRED_COLUMNS = {"a_au", "eccentricity", "inclination_deg"}


# ---------------------------------------------------------------------------
# Scalar helpers (used in tests and single-object lookups)
# ---------------------------------------------------------------------------


def tisserand_parameter(
    a: float,
    e: float,
    i_deg: float,
    a_j: float = A_JUPITER_AU,
) -> float:
    """
    Tisserand parameter with respect to Jupiter.

    Classifies orbit stability relative to Jupiter:
      T_J > 3   main-belt / non-Jupiter-crossing
      2 < T_J ≤ 3   Jupiter-family / accessible NEAs
      T_J ≤ 2   Halley-type / long-period comets

    Returns nan for invalid inputs (a ≤ 0 or e ≥ 1).
    """
    if a <= 0 or e < 0 or e >= 1 or not math.isfinite(a * e * i_deg):
        return float("nan")
    i_rad = math.radians(i_deg)
    return a_j / a + 2.0 * math.cos(i_rad) * math.sqrt((a / a_j) * (1.0 - e**2))


def delta_v_proxy_km_s(a: float, e: float, i_deg: float) -> float:  # noqa: ARG001
    """
    Simplified total delta-v proxy in km/s. See module docstring for formula.

    Eccentricity (e) is accepted for API consistency but not used in the
    delta-v calculation (circular-orbit approximation). Returns nan for a ≤ 0.
    """
    if a <= 0 or not math.isfinite(a * i_deg):
        return float("nan")
    i_rad = math.radians(i_deg)
    dv1 = V_EARTH_KM_S * abs(math.sqrt(2.0 * a / (1.0 + a)) - 1.0)
    dv2 = (V_EARTH_KM_S / math.sqrt(a)) * abs(1.0 - math.sqrt(2.0 / (1.0 + a)))
    v_mid = V_EARTH_KM_S * math.sqrt(2.0 / (1.0 + a))
    dv_inc = 2.0 * v_mid * math.sin(i_rad / 2.0)
    return math.sqrt(dv1**2 + dv2**2 + dv_inc**2)


def inclination_penalty(i_deg: float) -> float:
    """
    Normalised plane-change cost in [0, 1].

    Uses sin²(i/2) — the fractional velocity fraction required for a
    pure plane change at constant speed:
      0.0  coplanar with Earth (i = 0°)
      0.5  polar orbit (i = 90°)
      1.0  retrograde equatorial (i = 180°)
    """
    return math.sin(math.radians(i_deg) / 2.0) ** 2


# ---------------------------------------------------------------------------
# Vectorised DataFrame transformer
# ---------------------------------------------------------------------------


def add_orbital_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add orbital accessibility columns to the asteroid DataFrame.

    Required input columns : a_au, eccentricity, inclination_deg
    Added output columns   : tisserand_jupiter, delta_v_km_s, inclination_penalty

    Rows with any missing required value receive NaN in all added columns.
    All computation is vectorised over the valid subset for performance on
    the full catalog (~1.5 M rows).
    """
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    result = df.copy()
    for col in ("tisserand_jupiter", "delta_v_km_s", "inclination_penalty"):
        result[col] = np.nan

    notna = df[list(_REQUIRED_COLUMNS)].notna().all(axis=1)

    a_raw = df.loc[notna, "a_au"].to_numpy(dtype=float)
    e_raw = df.loc[notna, "eccentricity"].to_numpy(dtype=float)
    i_raw = df.loc[notna, "inclination_deg"].to_numpy(dtype=float)

    valid_mask = (
        np.isfinite(a_raw)
        & np.isfinite(e_raw)
        & np.isfinite(i_raw)
        & (a_raw > 0)
        & (e_raw >= 0)
        & (e_raw < 1)
    )

    mask = notna.copy()
    mask.loc[notna] = valid_mask

    a = a_raw[valid_mask]
    e = e_raw[valid_mask]
    i_rad = np.radians(i_raw[valid_mask])

    # Tisserand parameter
    inner = (a / A_JUPITER_AU) * (1.0 - e**2)
    result.loc[mask, "tisserand_jupiter"] = (
        A_JUPITER_AU / a + 2.0 * np.cos(i_rad) * np.sqrt(inner)
    )

    # Delta-v proxy
    dv1 = V_EARTH_KM_S * np.abs(np.sqrt(2.0 * a / (1.0 + a)) - 1.0)
    dv2 = (V_EARTH_KM_S / np.sqrt(a)) * np.abs(1.0 - np.sqrt(2.0 / (1.0 + a)))
    v_mid = V_EARTH_KM_S * np.sqrt(2.0 / (1.0 + a))
    dv_inc = 2.0 * v_mid * np.sin(i_rad / 2.0)
    result.loc[mask, "delta_v_km_s"] = np.sqrt(dv1**2 + dv2**2 + dv_inc**2)

    # Inclination penalty
    result.loc[mask, "inclination_penalty"] = np.sin(i_rad / 2.0) ** 2

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _latest_clean_parquet(processed_dir: Path) -> Path:
    candidates = sorted(processed_dir.glob("sbdb_clean_*.parquet"))
    if not candidates:
        raise FileNotFoundError(
            f"No sbdb_clean_*.parquet found in {processed_dir}. Run 'make clean-data' first."
        )
    return candidates[-1]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists())
    processed_dir = repo_root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    input_path = _latest_clean_parquet(processed_dir)
    logger.info("Reading %s", input_path.name)

    df = pd.read_parquet(input_path)
    logger.info("Loaded %d rows", len(df))

    result = add_orbital_features(df)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_orbital_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    valid = result["delta_v_km_s"].notna().sum()
    logger.info(
        "Saved %s — %d rows scored, %d skipped (invalid inputs), %.1fs",
        output_path.name,
        valid,
        len(result) - valid,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
