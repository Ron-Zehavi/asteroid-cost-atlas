"""
Composition proxy scoring with per-metal meteorite-analog resource model.

Infers asteroid resource class from taxonomy and/or albedo, then assigns
extractable resource estimates based on measured meteorite compositions.

Composition classes
-------------------
  C  — carbonaceous (CI/CM analogs): water-rich, trace precious metals
  S  — silicaceous (H/L chondrite): moderate metals, trace PGMs
  M  — metallic (iron meteorite): high Fe/Ni, significant PGMs
  V  — basaltic (HED achondrite): minimal resources
  U  — unknown: population average

Precious metal model
--------------------
Individual metal concentrations per class (ppm) from:
  Lodders, Bergemann & Palme (2025), arXiv:2502.10575
  Cannon, Gialich & Acain (2023), Planet. Space Sci. 225, 105608

Spot prices (2024–2025 averages) for selective extraction valuation.
A specimen-return mission extracts only precious metals — each returned
kg is priced at the refined metal rate, not the bulk rock average.

Sources
-------
  Cannon+ (2023): PGM in iron meteorites, 50th %ile total = 40.78 ppm
  Lodders+ (2025): CI chondrite bulk chemistry, PGM+Au = 3.375 ppm
  Garenne+ (2014): CI/CM/CR water content
  Dunn+ (2010): H/L/LL chondrite metal fractions
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from asteroid_cost_atlas.ingest.ingest_spectral import classify_from_sdss_colors

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy → composition class mapping
# ---------------------------------------------------------------------------

_TAXONOMY_MAP: dict[str, str] = {
    "C": "C", "B": "C", "F": "C", "G": "C", "D": "C", "T": "C",
    "CB": "C", "CG": "C", "CH": "C", "CX": "C",
    "S": "S", "K": "S", "L": "S", "A": "S", "Q": "S", "R": "S", "O": "S",
    "SA": "S", "SK": "S", "SL": "S", "SQ": "S", "SR": "S",
    "SE": "S", "SFC": "S",
    "M": "M", "X": "M", "E": "M", "P": "M", "XC": "M", "XE": "M",
    "V": "V",
}

# ---------------------------------------------------------------------------
# Per-metal concentration model (ppm by mass)
# ---------------------------------------------------------------------------

# Individual precious metal concentrations per composition class
# CI values: Lodders+ 2025 Table 4
# Iron values: Cannon+ 2023 (scaled from CI ratios × iron enrichment factor)
# S/V/U: interpolated from CI and metal fraction ratios

METALS: list[str] = ["platinum", "palladium", "rhodium", "iridium", "osmium", "ruthenium", "gold"]

# Spot prices in $/kg (April 2026 market data)
# Sources: Kitco (Apr 2, 2026), DailyMetalPrice (Mar 31, 2026)
# Conversion: $/troy oz × 32.1507 = $/kg
METAL_SPOT_PRICE: dict[str, float] = {
    "platinum":   63_300.0,   # $1,969/oz — Kitco Apr 2, 2026
    "palladium":  47_870.0,   # $1,489/oz — Kitco Apr 2, 2026
    "rhodium":   299_000.0,   # $9,300/oz — Kitco Apr 2, 2026
    "iridium":   254_000.0,   # $7,900/oz — DailyMetalPrice Mar 31, 2026
    "osmium":     12_860.0,   # ~$400/oz — raw commodity estimate
    "ruthenium":  56_260.0,   # $1,750/oz — DailyMetalPrice Mar 31, 2026
    "gold":      150_740.0,   # $4,690/oz — Kitco Apr 2, 2026
}

# Concentration in ppm per composition class
METAL_PPM: dict[str, dict[str, float]] = {
    "C": {
        "platinum": 0.90, "palladium": 0.56, "rhodium": 0.13,
        "iridium": 0.46, "osmium": 0.49, "ruthenium": 0.68, "gold": 0.15,
    },
    "S": {
        "platinum": 1.20, "palladium": 0.75, "rhodium": 0.17,
        "iridium": 0.61, "osmium": 0.65, "ruthenium": 0.90, "gold": 0.20,
    },
    "M": {
        "platinum": 15.0, "palladium": 8.0, "rhodium": 2.0,
        "iridium": 5.0, "osmium": 5.0, "ruthenium": 6.0, "gold": 1.0,
    },
    "V": {
        "platinum": 0.10, "palladium": 0.06, "rhodium": 0.01,
        "iridium": 0.05, "osmium": 0.05, "ruthenium": 0.07, "gold": 0.02,
    },
    "U": {
        "platinum": 1.50, "palladium": 0.90, "rhodium": 0.20,
        "iridium": 0.70, "osmium": 0.75, "ruthenium": 1.00, "gold": 0.25,
    },
}

# Extraction yield for precious metals (refining in space)
PRECIOUS_EXTRACTION_YIELD = 0.30

# Water and bulk metal parameters (kept for commodity model compatibility)
_WATER_WT_PCT: dict[str, float] = {"C": 15.0, "S": 0.0, "M": 0.0, "V": 0.0, "U": 1.5}
_METAL_WT_PCT: dict[str, float] = {"C": 19.7, "S": 28.9, "M": 98.6, "V": 15.0, "U": 25.0}
_WATER_PRICE_PER_KG = 500.0
_WATER_EXTRACTION_YIELD = 0.60
_METAL_PRICE_PER_KG = 50.0
_METAL_EXTRACTION_YIELD = 0.50

# Albedo thresholds
_ALBEDO_LOW = 0.10
_ALBEDO_MID = 0.20
_ALBEDO_HIGH = 0.35


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def classify_taxonomy(taxonomy: str | None) -> str:
    """Map a taxonomy string to a composition class (C/S/M/V/U)."""
    if taxonomy is None or not isinstance(taxonomy, str):
        return "U"
    clean = taxonomy.strip().rstrip("*:").upper()
    if clean in _TAXONOMY_MAP:
        return _TAXONOMY_MAP[clean]
    if clean and clean[0] in _TAXONOMY_MAP:
        return _TAXONOMY_MAP[clean[0]]
    return "U"


def classify_albedo(albedo: float) -> str:
    """Infer composition class from albedo alone."""
    if not math.isfinite(albedo) or albedo <= 0:
        return "U"
    if albedo < _ALBEDO_LOW:
        return "C"
    if albedo < _ALBEDO_MID:
        return "S"
    if albedo < _ALBEDO_HIGH:
        return "S"
    return "V"


def specimen_value_per_kg(composition_class: str) -> float:
    """
    Value of 1 kg of refined precious metal concentrate from this class.

    Weighted by individual metal concentrations and spot prices.
    This is what a specimen-return mission would earn per kg returned.
    """
    c = composition_class if composition_class in METAL_PPM else "U"
    ppm = METAL_PPM[c]
    total_ppm = sum(ppm.values())
    if total_ppm == 0:
        return 0.0
    # Weighted average price based on relative concentration
    weighted_price = sum(
        (ppm[m] / total_ppm) * METAL_SPOT_PRICE[m] for m in METALS
    )
    return round(weighted_price, 2)


def resource_value_per_kg(composition_class: str) -> float:
    """Total commodity value per kg of raw asteroid material (water + metals + precious)."""
    c = composition_class if composition_class in _WATER_WT_PCT else "U"
    water = (_WATER_WT_PCT[c] / 100.0) * _WATER_EXTRACTION_YIELD * _WATER_PRICE_PER_KG
    metals = (_METAL_WT_PCT[c] / 100.0) * _METAL_EXTRACTION_YIELD * _METAL_PRICE_PER_KG
    ppm = METAL_PPM.get(c, METAL_PPM["U"])
    precious = sum(
        (ppm[m] / 1e6) * PRECIOUS_EXTRACTION_YIELD * METAL_SPOT_PRICE[m]
        for m in METALS
    )
    return round(water + metals + precious, 2)


def resource_breakdown(composition_class: str) -> dict[str, float]:
    """Detailed commodity value breakdown per kg."""
    c = composition_class if composition_class in _WATER_WT_PCT else "U"
    water = (_WATER_WT_PCT[c] / 100.0) * _WATER_EXTRACTION_YIELD * _WATER_PRICE_PER_KG
    metals = (_METAL_WT_PCT[c] / 100.0) * _METAL_EXTRACTION_YIELD * _METAL_PRICE_PER_KG
    ppm = METAL_PPM.get(c, METAL_PPM["U"])
    precious = sum(
        (ppm[m] / 1e6) * PRECIOUS_EXTRACTION_YIELD * METAL_SPOT_PRICE[m]
        for m in METALS
    )
    return {
        "water_usd_per_kg": round(water, 4),
        "metals_usd_per_kg": round(metals, 4),
        "precious_usd_per_kg": round(precious, 4),
        "total_usd_per_kg": round(water + metals + precious, 2),
    }


# ---------------------------------------------------------------------------
# Vectorised DataFrame transformer
# ---------------------------------------------------------------------------


def add_composition_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add composition proxy columns to the asteroid DataFrame.

    Added columns:
      - composition_class, composition_source
      - resource_value_usd_per_kg, water/metals/precious breakdown
      - specimen_value_per_kg (refined concentrate spot price)
      - per-metal extractable kg (requires estimated_mass_kg from economic stage)
    """
    result = df.copy()
    n = len(df)
    comp_class = np.full(n, "U", dtype=object)
    comp_source = np.full(n, "none", dtype=object)

    # Layer 1: taxonomy
    if "taxonomy" in df.columns:
        tax_vals = df["taxonomy"].values
        has_tax = pd.notna(tax_vals)
        if has_tax.any():
            mapped = np.array([classify_taxonomy(str(v)) for v in tax_vals[has_tax]])
            found = mapped != "U"
            positions = np.where(has_tax)[0][found]
            comp_class[positions] = mapped[found]
            comp_source[positions] = "taxonomy"

    # Layer 2: spectral_type
    if "spectral_type" in df.columns:
        spec_vals = df["spectral_type"].values
        still_unknown = comp_class == "U"
        has_spec = pd.notna(spec_vals) & still_unknown
        if has_spec.any():
            mapped = np.array([classify_taxonomy(str(v)) for v in spec_vals[has_spec]])
            found = mapped != "U"
            positions = np.where(has_spec)[0][found]
            comp_class[positions] = mapped[found]
            comp_source[positions] = "taxonomy"

    # Layer 3: SDSS color indices
    if "color_gr" in df.columns and "color_ri" in df.columns:
        gr_vals = df["color_gr"].to_numpy(dtype=float, na_value=np.nan)
        ri_vals = df["color_ri"].to_numpy(dtype=float, na_value=np.nan)
        still_unknown = comp_class == "U"
        has_colors = np.isfinite(gr_vals) & np.isfinite(ri_vals) & still_unknown
        if has_colors.any():
            mapped = np.array([
                classify_from_sdss_colors(float(gr), float(ri))
                for gr, ri in zip(gr_vals[has_colors], ri_vals[has_colors])
            ])
            found = mapped != "U"
            positions = np.where(has_colors)[0][found]
            comp_class[positions] = mapped[found]
            comp_source[positions] = "sdss_colors"

    # Layer 4: albedo
    if "albedo" in df.columns:
        alb_vals = df["albedo"].to_numpy(dtype=float, na_value=np.nan)
        still_unknown = comp_class == "U"
        has_albedo = np.isfinite(alb_vals) & (alb_vals > 0) & still_unknown
        if has_albedo.any():
            mapped = np.array([classify_albedo(float(v)) for v in alb_vals[has_albedo]])
            found = mapped != "U"
            positions = np.where(has_albedo)[0][found]
            comp_class[positions] = mapped[found]
            comp_source[positions] = "albedo"

    result["composition_class"] = comp_class
    result["composition_source"] = comp_source

    # Commodity breakdown
    value_map = np.vectorize(resource_value_per_kg)
    result["resource_value_usd_per_kg"] = value_map(comp_class)

    breakdowns = [resource_breakdown(c) for c in comp_class]
    result["water_value_usd_per_kg"] = [b["water_usd_per_kg"] for b in breakdowns]
    result["metals_value_usd_per_kg"] = [b["metals_usd_per_kg"] for b in breakdowns]
    result["precious_value_usd_per_kg"] = [b["precious_usd_per_kg"] for b in breakdowns]

    # Specimen value per kg (weighted by individual metal prices)
    specimen_map = np.vectorize(specimen_value_per_kg)
    result["specimen_value_per_kg"] = specimen_map(comp_class)

    # Per-metal ppm columns (for downstream extractable kg calculation)
    for metal in METALS:
        ppm_vals = np.array([
            METAL_PPM.get(c, METAL_PPM["U"])[metal] for c in comp_class
        ])
        result[f"{metal}_ppm"] = ppm_vals

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _latest_physical_parquet(processed_dir: Path) -> Path:
    for pattern in ("sbdb_physical_*.parquet", "sbdb_orbital_*.parquet"):
        candidates = sorted(processed_dir.glob(pattern))
        if candidates:
            return candidates[-1]
    raise FileNotFoundError(
        f"No scored parquet found in {processed_dir}. "
        "Run 'make score-physical' first."
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(
        p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists()
    )
    processed_dir = repo_root / "data" / "processed"

    input_path = _latest_physical_parquet(processed_dir)
    logger.info("Reading %s", input_path.name)

    df = pd.read_parquet(input_path)
    logger.info("Loaded %d rows", len(df))

    result = add_composition_features(df)

    counts = result["composition_class"].value_counts().to_dict()

    for cls in ("C", "S", "M", "V", "U"):
        sv = specimen_value_per_kg(cls)
        cv = resource_value_per_kg(cls)
        logger.info("  %s: specimen=$%.0f/kg, commodity=$%.2f/kg", cls, sv, cv)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_composition_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — classes: %s | %.1fs",
        output_path.name, counts,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
