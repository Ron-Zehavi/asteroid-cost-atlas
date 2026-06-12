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

Campaign model
--------------
  Fixed-capacity missions (MISSION_CAPACITY_KG), filled greedily by spot
  $/kg from an inventory capped at the extraction-limit fraction; the
  campaign stops when the next mission would be unprofitable. Mirrors the
  web model in web/src/utils/mining.ts — see docs/VALUATION_RECONCILIATION.md
  for the discrepancy this replaced.

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
import numpy.typing as npt
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
# Fixed payload per campaign mission. Matches the web model's
# DEFAULT_MISSION_KG so pipeline and UI agree (docs/VALUATION_RECONCILIATION.md).
MISSION_CAPACITY_KG = 100_000.0

# Extraction-limit caps on mineable mass fraction (mirrors web/src/utils/mining.ts):
# Sanchez & Scheeres (2014) rubble-pile disruption ~40%; engineering cap 30%.
STRUCTURAL_LIMIT = 0.40
OPERATIONAL_LIMIT = 0.30

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


def extraction_limit_fraction(
    rotation_hours: float,
    diameter_km: float,
    surface_gravity_m_s2: float,
) -> float:
    """Mineable fraction of asteroid mass before rubble-pile destabilization.

    min(f_rotation, structural 40%, operational 30%), where f_rotation =
    1 - centrifugal/gravity at the equator. Falls back to the operational
    limit when inputs are missing so scenarios are never silently uncapped.
    """
    if (
        not math.isfinite(rotation_hours) or rotation_hours <= 0
        or not math.isfinite(diameter_km) or diameter_km <= 0
        or not math.isfinite(surface_gravity_m_s2) or surface_gravity_m_s2 <= 0
    ):
        return OPERATIONAL_LIMIT
    omega = (2.0 * math.pi) / (rotation_hours * 3600.0)
    radius_m = (diameter_km * 1000.0) / 2.0
    f_rotation = max(0.0, 1.0 - (omega * omega * radius_m) / surface_gravity_m_s2)
    return min(f_rotation, STRUCTURAL_LIMIT, OPERATIONAL_LIMIT)


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
        ext_by_metal: dict[str, npt.NDArray[np.float64]] = {}

        for metal in METALS:
            price = METAL_SPOT_PRICE[metal]
            ppm_col = f"{metal}_ppm"
            if ppm_col in df.columns:
                ppm = df.loc[has_data, ppm_col].to_numpy(dtype=float)[valid]
            else:
                ppm = np.zeros_like(mass)

            ext_kg = mass * (ppm / 1e6) * PRECIOUS_EXTRACTION_YIELD
            ext_val = ext_kg * price
            ext_by_metal[metal] = ext_kg
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

        # --- Campaign: greedy fixed-capacity missions ---
        # Mirrors the web model (web/src/utils/mining.ts); see
        # docs/VALUATION_RECONCILIATION.md for why the previous break-even
        # sizing made campaign profit a floor-division residue.
        #   * inventory capped by the extraction-limit fraction
        #   * missions of MISSION_CAPACITY_KG, filled highest-$/kg metal first
        #   * campaign stops when the next mission would be unprofitable
        f_max = np.full_like(mass, OPERATIONAL_LIMIT)
        if "rotation_hours" in df.columns and "surface_gravity_m_s2" in df.columns:
            rot = df.loc[has_data, "rotation_hours"].to_numpy(dtype=float)[valid]
            grav = df.loc[has_data, "surface_gravity_m_s2"].to_numpy(dtype=float)[valid]
            ok = np.isfinite(rot) & (rot > 0) & np.isfinite(grav) & (grav > 0)
            omega = (2.0 * np.pi) / (rot[ok] * 3600.0)
            radius_ok = (d[ok] * 1000.0) / 2.0
            f_rot = np.maximum(0.0, 1.0 - (omega * omega * radius_ok) / grav[ok])
            f_max[ok] = np.minimum(
                np.minimum(f_rot, STRUCTURAL_LIMIT), OPERATIONAL_LIMIT
            )

        # Capped per-metal inventory, ordered by spot price descending. The
        # cumulative value of the first x kg is then piecewise linear, which
        # lets every mission's revenue be evaluated in O(#metals).
        greedy_order = sorted(METALS, key=lambda m: METAL_SPOT_PRICE[m], reverse=True)
        widths = np.stack(
            [ext_by_metal[m] * f_max for m in greedy_order], axis=1
        )
        prices = np.array([METAL_SPOT_PRICE[m] for m in greedy_order])
        bounds = np.cumsum(widths, axis=1)
        lowers = bounds - widths
        total_capped = bounds[:, -1]

        def value_at(
            rows: npt.NDArray[np.intp], x: npt.NDArray[np.float64]
        ) -> npt.NDArray[np.float64]:
            """$ value of the first x kg of capped inventory for these rows."""
            seg = np.clip(x[:, None] - lowers[rows], 0.0, widths[rows])
            return np.asarray(seg @ prices, dtype=np.float64)

        cap = MISSION_CAPACITY_KG
        fixed = MISSION_MIN_COST + MISSION_SYSTEM_MASS_KG * transport
        var_per_kg = transport + EXTRACTION_OVERHEAD
        all_rows = np.arange(mass.shape[0])

        # Full missions: profit of mission k is non-increasing in k (the value
        # function is concave), so binary-search the last profitable mission.
        n_full = np.floor(total_capped / cap)
        first_profit = (
            value_at(all_rows, np.minimum(cap, np.nan_to_num(total_capped)))
            - fixed
            - np.minimum(cap, total_capped) * var_per_kg
        )
        first_full_ok = (n_full >= 1) & (
            value_at(all_rows, np.full_like(mass, cap)) - fixed - cap * var_per_kg > 0
        )
        k_lo = np.where(first_full_ok, 1.0, 0.0)
        k_hi = np.where(first_full_ok, n_full, 0.0)
        while True:
            active = np.flatnonzero(k_lo < k_hi)
            if active.size == 0:
                break
            mid = np.ceil((k_lo[active] + k_hi[active]) / 2.0)
            profit_mid = (
                value_at(active, mid * cap)
                - value_at(active, (mid - 1.0) * cap)
                - fixed[active]
                - cap * var_per_kg[active]
            )
            good = profit_mid > 0
            k_lo[active[good]] = mid[good]
            k_hi[active[~good]] = mid[~good] - 1.0
        k_full = k_lo

        # Trailing partial mission (also the only mission when total < cap).
        remainder = total_capped - n_full * cap
        partial_mask = (remainder > 0.01) & (k_full == n_full)
        partial_payload = np.where(partial_mask, remainder, 0.0)
        partial_profit = (
            value_at(all_rows, total_capped)
            - value_at(all_rows, n_full * cap)
            - fixed
            - partial_payload * var_per_kg
        )
        partial_ok = partial_mask & (partial_profit > 0)

        n_missions = k_full + partial_ok.astype(float)
        end_kg = k_full * cap + np.where(partial_ok, partial_payload, 0.0)
        camp_rev = value_at(all_rows, end_kg)
        camp_cost = k_full * (fixed + cap * var_per_kg) + np.where(
            partial_ok, fixed + partial_payload * var_per_kg, 0.0
        )
        has_mission = n_missions > 0

        result.loc[mask, "missions_supported"] = n_missions

        # Per-mission columns report the FIRST (best) mission — the flagship
        # number; later missions only get cheaper metals.
        first_payload = np.minimum(cap, total_capped)
        first_rev = value_at(all_rows, first_payload)
        first_cost = fixed + first_payload * var_per_kg
        result.loc[mask, "mission_revenue_usd"] = np.where(
            has_mission, first_rev, np.nan
        )
        result.loc[mask, "mission_cost_usd"] = np.where(
            has_mission, first_cost, np.nan
        )
        result.loc[mask, "mission_profit_usd"] = np.where(
            has_mission, first_profit, np.nan
        )

        result.loc[mask, "campaign_revenue_usd"] = np.where(
            has_mission, camp_rev, np.nan
        )
        result.loc[mask, "campaign_cost_usd"] = np.where(
            has_mission, camp_cost, np.nan
        )
        result.loc[mask, "campaign_profit_usd"] = np.where(
            has_mission, camp_rev - camp_cost, np.nan
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
