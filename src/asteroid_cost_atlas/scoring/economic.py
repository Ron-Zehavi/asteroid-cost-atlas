"""
Economic scoring and atlas assembly.

Subsystem-based mission cost model with per-metal break-even analysis.

Mission cost structure
----------------------
  mission_min_cost = $300M (spacecraft + mining payload + autonomy +
                    I&T + operations reserve)
                    Calibrated from Discovery-class analogs.

  total_cost = mission_min_cost
             + system_mass × transport_per_kg
             + extracted_mass × extraction_overhead

  margin_per_kg = specimen_value - transport_cost - extraction_overhead
  break_even_kg = mission_min_cost / margin_per_kg

Per-metal break-even
--------------------
  For each metal, the break-even mass tells you how many kg of that
  specific metal you need to extract to cover the $300M mission cost:
    break_even_{metal}_kg = mission_min_cost / (metal_price - transport - extraction)

  This answers: "to justify a mission to asteroid X, you need to extract
  at least Y kg of gold (or Z kg of platinum, etc.)"

Spot prices updated April 2, 2026 from Kitco and DailyMetalPrice.

References
----------
  Cannon+ (2023), Lodders+ (2025), Sonter (1997), Elvis (2014)
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from asteroid_cost_atlas.scoring.composition import (
    METAL_SPOT_PRICE,
    METALS,
    PRECIOUS_EXTRACTION_YIELD,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DENSITY: dict[str, float] = {
    "C": 1300.0, "S": 2700.0, "M": 5300.0, "V": 3500.0, "U": 2000.0,
}

FALCON_LEO_COST = 2700.0
ISP = 320.0
G0 = 9.81
VE = ISP * G0 / 1000.0

MISSION_MIN_COST = 300_000_000.0
MISSION_SYSTEM_MASS_KG = 1_000.0
EXTRACTION_OVERHEAD = 5_000.0
MISSION_CAPACITY_KG = 1_000.0

_REQUIRED_COLUMNS = {
    "diameter_estimated_km", "delta_v_km_s",
    "composition_class", "resource_value_usd_per_kg",
    "specimen_value_per_kg",
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
    """Round-trip transport cost per kg: $2,700 × exp(2 × dv / Ve)."""
    if delta_v_km_s <= 0 or not math.isfinite(delta_v_km_s):
        return float("nan")
    return FALCON_LEO_COST * math.exp(2.0 * delta_v_km_s / VE)


def accessibility_score(delta_v_km_s: float) -> float:
    """Accessibility as inverse square of delta-v."""
    if delta_v_km_s <= 0 or not math.isfinite(delta_v_km_s):
        return float("nan")
    return 1.0 / (delta_v_km_s ** 2)


# ---------------------------------------------------------------------------
# Vectorised DataFrame transformer
# ---------------------------------------------------------------------------


def add_economic_score(df: pd.DataFrame) -> pd.DataFrame:
    """Add economic scoring columns and rank the atlas."""
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    result = df.copy()

    base_cols = [
        "estimated_mass_kg", "mission_cost_usd_per_kg", "accessibility",
        "total_extractable_precious_kg", "total_precious_value_usd",
        "margin_per_kg", "break_even_kg", "min_viable_kg",
        "is_viable", "missions_supported",
        "mission_revenue_usd", "mission_cost_usd", "mission_profit_usd",
        "campaign_revenue_usd", "campaign_cost_usd", "campaign_profit_usd",
        "economic_score",
    ]
    metal_ext_cols = [f"extractable_{m}_kg" for m in METALS]
    metal_be_cols = [f"break_even_{m}_kg" for m in METALS]
    for col in base_cols + metal_ext_cols + metal_be_cols:
        result[col] = np.nan
    result["is_viable"] = False

    has_data = df["diameter_estimated_km"].notna() & df["delta_v_km_s"].notna()

    if has_data.any():
        d_km = df.loc[has_data, "diameter_estimated_km"].to_numpy(dtype=float)
        dv = df.loc[has_data, "delta_v_km_s"].to_numpy(dtype=float)
        comp = df.loc[has_data, "composition_class"].to_numpy()
        sv_pkg = df.loc[has_data, "specimen_value_per_kg"].to_numpy(dtype=float)

        valid = np.isfinite(d_km) & np.isfinite(dv) & (d_km > 0) & (dv > 0)
        mask = has_data.copy()
        mask.loc[has_data] = valid

        d = d_km[valid]
        v = dv[valid]
        c = comp[valid]
        sv = sv_pkg[valid]

        # --- Mass ---
        densities = np.array([_DENSITY.get(cls, _DENSITY["U"]) for cls in c])
        radius_m = (d * 1000.0) / 2.0
        mass = densities * (4.0 / 3.0) * np.pi * radius_m ** 3

        # --- Transport ---
        transport = FALCON_LEO_COST * np.exp(2.0 * v / VE)
        access = 1.0 / (v ** 2)

        result.loc[mask, "estimated_mass_kg"] = mass
        result.loc[mask, "mission_cost_usd_per_kg"] = transport
        result.loc[mask, "accessibility"] = access

        # --- Per-metal extractable kg + per-metal break-even ---
        total_precious_kg = np.zeros_like(mass)
        total_precious_val = np.zeros_like(mass)

        for metal in METALS:
            price = METAL_SPOT_PRICE[metal]
            ppm_col = f"{metal}_ppm"
            if ppm_col in df.columns:
                ppm = df.loc[has_data, ppm_col].to_numpy(dtype=float)[valid]
            else:
                ppm = np.zeros_like(mass)

            ext_kg = mass * (ppm / 1e6) * PRECIOUS_EXTRACTION_YIELD
            ext_val = ext_kg * price
            result.loc[mask, f"extractable_{metal}_kg"] = ext_kg
            total_precious_kg += ext_kg
            total_precious_val += ext_val

            # Per-metal break-even: kg of this metal to cover full fixed cost
            metal_margin = price - transport - EXTRACTION_OVERHEAD
            be_metal = np.full_like(metal_margin, np.nan)
            pos = metal_margin > 0
            metal_fixed = MISSION_MIN_COST + MISSION_SYSTEM_MASS_KG * transport
            be_metal[pos] = metal_fixed[pos] / metal_margin[pos]
            result.loc[mask, f"break_even_{metal}_kg"] = be_metal

        result.loc[mask, "total_extractable_precious_kg"] = total_precious_kg
        result.loc[mask, "total_precious_value_usd"] = total_precious_val

        # --- Overall margin and break-even (weighted specimen value) ---
        margin = sv - transport - EXTRACTION_OVERHEAD
        result.loc[mask, "margin_per_kg"] = margin

        # Total fixed cost = mission minimum + getting the mining system there
        total_fixed = MISSION_MIN_COST + MISSION_SYSTEM_MASS_KG * transport
        be = np.full_like(margin, np.nan)
        positive_margin = margin > 0
        be[positive_margin] = total_fixed[positive_margin] / margin[positive_margin]
        result.loc[mask, "break_even_kg"] = be

        min_viable = np.full_like(be, np.nan)
        min_viable[positive_margin] = np.maximum(
            be[positive_margin], MISSION_SYSTEM_MASS_KG
        )
        result.loc[mask, "min_viable_kg"] = min_viable

        # Viable = asteroid has enough material for at least one
        # full break-even payload
        viable = positive_margin & np.isfinite(be) & (total_precious_kg >= be)
        result.loc[mask, "is_viable"] = viable

        # --- Campaign: only profitable missions ---
        # A mission is profitable when its payload ≥ break_even_kg.
        # Number of missions = floor(extractable / break_even_kg).
        # Only count missions where each one carries ≥ break_even_kg.
        n_missions = np.zeros_like(mass)
        mission_payload = np.zeros_like(mass)

        if viable.any():
            be_viable = be[viable]
            ext_viable = total_precious_kg[viable]
            # How many full break-even loads fit?
            n = np.floor(ext_viable / be_viable)
            n_missions[viable] = n
            # Distribute ALL extractable evenly across missions.
            # Each mission carries extractable/n > break_even (guaranteed
            # because n = floor(ext/be), so ext/n >= be).
            mission_payload[viable] = ext_viable / np.maximum(n, 1.0)

        result.loc[mask, "missions_supported"] = n_missions

        # Per-mission economics (each mission is individually profitable)
        per_mission_rev = mission_payload * sv
        per_mission_cost = (
            MISSION_MIN_COST
            + MISSION_SYSTEM_MASS_KG * transport
            + mission_payload * (transport + EXTRACTION_OVERHEAD)
        )
        per_mission_profit = per_mission_rev - per_mission_cost

        result.loc[mask, "mission_revenue_usd"] = np.where(
            n_missions > 0, per_mission_rev, np.nan
        )
        result.loc[mask, "mission_cost_usd"] = np.where(
            n_missions > 0, per_mission_cost, np.nan
        )
        result.loc[mask, "mission_profit_usd"] = np.where(
            n_missions > 0, per_mission_profit, np.nan
        )

        # Campaign totals (sum of all profitable missions)
        campaign_rev = n_missions * per_mission_rev
        campaign_cost = n_missions * per_mission_cost
        campaign_profit = n_missions * per_mission_profit

        result.loc[mask, "campaign_revenue_usd"] = np.where(
            n_missions > 0, campaign_rev, np.nan
        )
        result.loc[mask, "campaign_cost_usd"] = np.where(
            n_missions > 0, campaign_cost, np.nan
        )
        result.loc[mask, "campaign_profit_usd"] = np.where(
            n_missions > 0, campaign_profit, np.nan
        )

        # --- Economic score ---
        result.loc[mask, "economic_score"] = total_precious_val * access

    # Rank
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
        result.loc[ranked.index, "economic_priority_rank"] = range(
            1, len(ranked) + 1
        )

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
        p for p in [_module, *_module.parents]
        if (p / "pyproject.toml").exists()
    )
    processed_dir = repo_root / "data" / "processed"

    input_path = _latest_composition_parquet(processed_dir)
    logger.info("Reading %s", input_path.name)

    df = pd.read_parquet(input_path)
    logger.info("Loaded %d rows", len(df))

    result = add_economic_score(df)

    margin_pos = (result["margin_per_kg"] > 0).sum()
    viable = result["is_viable"].sum()
    total_missions = result.loc[result["is_viable"], "missions_supported"].sum()

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"atlas_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info("Margin > 0: %d asteroids", margin_pos)
    logger.info("Viable (enough material): %d asteroids", viable)
    logger.info("Total missions supported: %.0f", total_missions)
    logger.info(
        "Saved %s — %.1fs", output_path.name, time.perf_counter() - started
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
