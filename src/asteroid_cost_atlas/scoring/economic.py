"""
Economic scoring and atlas assembly.

Combines all upstream features into a single economic accessibility
score and produces the final ranked atlas dataset.

Economic model
--------------
Four components:

1. **Estimated mass** (kg):
       mass = density × (4/3) × π × (D/2)³

   Density by composition class:
     C: 1,300 kg/m³  (carbonaceous chondrites)
     S: 2,700 kg/m³  (ordinary chondrites)
     M: 5,300 kg/m³  (iron meteorites)
     V: 3,500 kg/m³  (HED achondrites)
     U: 2,000 kg/m³  (population average)

2. **Estimated total value** (USD):
       value = mass × resource_value_usd_per_kg

   Resource values come from the meteorite-analog model in
   composition.py (Cannon+ 2023, Lodders+ 2025).

3. **Mission cost proxy** (USD/kg delivered):
       cost_per_kg = LEO_launch_cost × exp(2 × dv / Ve)

   Based on Tsiolkovsky rocket equation:
     LEO launch cost: $2,700/kg (Falcon Heavy, 2024 pricing)
     Specific impulse: 320 s (bipropellant)
     Round-trip factor: 2× (outbound + return)

4. **Economic score** (USD·accessibility):
       economic_score = value × (1 / dv²)

   The ranking sorts by this score descending:
   "Which asteroid offers the most value for the least mission energy?"

All estimates carry large uncertainties — suitable for comparative
ranking, not absolute cost/revenue projections.

References
----------
  Cannon, Gialich & Acain (2023), Planet. Space Sci. 225, 105608
  Lodders, Bergemann & Palme (2025), arXiv:2502.10575
  Sonter (1997); Sanchez & McInnes (2013); Elvis (2014)
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Bulk density by composition class (kg/m³)
_DENSITY: dict[str, float] = {
    "C": 1300.0,
    "S": 2700.0,
    "M": 5300.0,
    "V": 3500.0,
    "U": 2000.0,
}

# Mission cost model parameters
LEO_COST_PER_KG = 2700.0    # $/kg to LEO (Falcon Heavy, 2024)
ISP = 320.0                  # seconds (bipropellant)
G0 = 9.81                   # m/s²
VE = ISP * G0 / 1000.0      # exhaust velocity in km/s

_REQUIRED_COLUMNS = {
    "diameter_estimated_km",
    "delta_v_km_s",
    "composition_class",
    "resource_value_usd_per_kg",
}


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def estimated_mass_kg(diameter_km: float, composition_class: str) -> float:
    """Estimate asteroid mass in kg assuming a sphere with class-specific density."""
    if diameter_km <= 0 or not math.isfinite(diameter_km):
        return float("nan")
    density = _DENSITY.get(composition_class, _DENSITY["U"])
    radius_m = (diameter_km * 1000.0) / 2.0
    return density * (4.0 / 3.0) * math.pi * radius_m ** 3


def mission_cost_per_kg(delta_v_km_s: float) -> float:
    """
    Estimated round-trip cost per kg delivered (USD).

    Uses Tsiolkovsky equation: cost = LEO_cost × exp(2 × dv / Ve).
    """
    if delta_v_km_s <= 0 or not math.isfinite(delta_v_km_s):
        return float("nan")
    return LEO_COST_PER_KG * math.exp(2.0 * delta_v_km_s / VE)


def accessibility_score(delta_v_km_s: float) -> float:
    """Accessibility as inverse square of delta-v. Higher = more accessible."""
    if delta_v_km_s <= 0 or not math.isfinite(delta_v_km_s):
        return float("nan")
    return 1.0 / (delta_v_km_s ** 2)


def economic_score(
    mass_kg: float, value_per_kg: float, access: float
) -> float:
    """Composite economic score: value × accessibility."""
    if not math.isfinite(mass_kg * value_per_kg * access):
        return float("nan")
    return mass_kg * value_per_kg * access


# ---------------------------------------------------------------------------
# Vectorised DataFrame transformer
# ---------------------------------------------------------------------------


def add_economic_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add economic scoring columns and rank the atlas.

    Required input columns: diameter_estimated_km, delta_v_km_s,
                            composition_class, resource_value_usd_per_kg

    Added columns:
      - ``estimated_mass_kg``
      - ``estimated_value_usd``
      - ``mission_cost_usd_per_kg`` — round-trip delivery cost
      - ``profit_ratio`` — resource_value / mission_cost (>1 = profitable)
      - ``accessibility``
      - ``economic_score``
      - ``economic_priority_rank`` (1 = best)
    """
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    result = df.copy()
    for col in (
        "estimated_mass_kg", "estimated_value_usd",
        "mission_cost_usd_per_kg", "profit_ratio",
        "accessibility", "economic_score",
    ):
        result[col] = np.nan

    # Valid rows: have both diameter and delta-v
    has_data = df["diameter_estimated_km"].notna() & df["delta_v_km_s"].notna()

    if has_data.any():
        d_km = df.loc[has_data, "diameter_estimated_km"].to_numpy(dtype=float)
        dv = df.loc[has_data, "delta_v_km_s"].to_numpy(dtype=float)
        comp = df.loc[has_data, "composition_class"].to_numpy()
        vpkg = df.loc[has_data, "resource_value_usd_per_kg"].to_numpy(dtype=float)

        valid = np.isfinite(d_km) & np.isfinite(dv) & (d_km > 0) & (dv > 0)
        mask = has_data.copy()
        mask.loc[has_data] = valid

        d = d_km[valid]
        v = dv[valid]
        c = comp[valid]
        val = vpkg[valid]

        # Mass: density × (4/3)π r³
        densities = np.array([_DENSITY.get(cls, _DENSITY["U"]) for cls in c])
        radius_m = (d * 1000.0) / 2.0
        mass = densities * (4.0 / 3.0) * np.pi * radius_m ** 3

        # Value and cost
        total_value = mass * val
        cost = LEO_COST_PER_KG * np.exp(2.0 * v / VE)
        profit = val / cost
        access = 1.0 / (v ** 2)
        score = total_value * access

        result.loc[mask, "estimated_mass_kg"] = mass
        result.loc[mask, "estimated_value_usd"] = total_value
        result.loc[mask, "mission_cost_usd_per_kg"] = cost
        result.loc[mask, "profit_ratio"] = profit
        result.loc[mask, "accessibility"] = access
        result.loc[mask, "economic_score"] = score

    # Rank: highest economic_score = rank 1, ties broken by name
    scored = result["economic_score"].notna()
    result["economic_priority_rank"] = np.nan
    if scored.any():
        sort_cols = ["economic_score"]
        ascending = [False]
        if "name" in result.columns:
            sort_cols.append("name")
            ascending.append(True)
        ranked = (
            result.loc[scored, sort_cols]
            .sort_values(sort_cols, ascending=ascending)
        )
        result.loc[ranked.index, "economic_priority_rank"] = range(1, len(ranked) + 1)

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _latest_composition_parquet(processed_dir: Path) -> Path:
    candidates = sorted(processed_dir.glob("sbdb_composition_*.parquet"))
    if not candidates:
        raise FileNotFoundError(
            f"No sbdb_composition_*.parquet found in {processed_dir}. "
            "Run 'make score-composition' first."
        )
    return candidates[-1]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(
        p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists()
    )
    processed_dir = repo_root / "data" / "processed"

    input_path = _latest_composition_parquet(processed_dir)
    logger.info("Reading %s", input_path.name)

    df = pd.read_parquet(input_path)
    logger.info("Loaded %d rows", len(df))

    result = add_economic_score(df)

    scored = result["economic_score"].notna().sum()
    profitable = (result["profit_ratio"] > 1.0).sum()
    top = result.nsmallest(1, "economic_priority_rank")
    top_name = top["name"].iloc[0] if len(top) else "N/A"

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"atlas_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — %d scored, %d profitable (ratio>1), #1: %s, %.1fs",
        output_path.name,
        scored,
        profitable,
        top_name,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
