"""
Composition proxy scoring with meteorite-analog resource model.

Infers asteroid resource class from taxonomy and/or albedo, then assigns
resource value estimates based on measured meteorite compositions.

Composition classes
-------------------
  C  — carbonaceous: water-rich, low PGMs (CI/CM analogs)
  S  — silicaceous: moderate metals, trace PGMs (H/L/LL chondrite analogs)
  M  — metallic: high iron/nickel, significant PGMs (iron meteorite analogs)
  V  — basaltic: pyroxene/feldspar, minimal resources (HED analogs)
  U  — unknown: no taxonomy or albedo available — uses population average

Classification priority:
  1. LCDB/SBDB taxonomy → direct mapping
  2. Albedo range → probabilistic inference
  3. Neither available → "U" (unknown)

Resource model (per kg of raw asteroid material)
-------------------------------------------------
Three resource groups are valued separately:

  **Water** — in-space propellant value (H₂+O₂ electrolysis).
    Extraction yield ~60%. Value $500/kg in cislunar space.
    Only C-types carry significant water (10–20 wt% for CI analogs).

  **Bulk metals** — iron, nickel, cobalt for in-space construction.
    Value $50/kg in orbit (vs ~$0.50/kg on Earth surface).
    All classes carry some iron; M-types are ~91% metal.

  **Precious metals** — PGMs (Pt, Pd, Ir, Os, Ru, Rh) + Au.
    Earth-return commodity value at spot prices (~$35,000/kg average).
    Concentrations from Cannon et al. (2023): iron meteorites
    median 40.8 ppm total PGM; CI chondrites ~3.2 ppm.

Sources
-------
  Cannon, Gialich & Acain (2023), Planet. Space Sci. 225, 105608
  Lodders, Bergemann & Palme (2025), arXiv:2502.10575
  Garenne et al. (2014), Geochim. Cosmochim. Acta 137, 93–112
  Dunn et al. (2010), Icarus 208, 789–797
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

# ---------------------------------------------------------------------------
# Taxonomy → composition class mapping
# ---------------------------------------------------------------------------

_TAXONOMY_MAP: dict[str, str] = {
    # Carbonaceous
    "C": "C", "B": "C", "F": "C", "G": "C", "D": "C", "T": "C",
    "CB": "C", "CG": "C", "CH": "C", "CX": "C",
    # Silicaceous
    "S": "S", "K": "S", "L": "S", "A": "S", "Q": "S", "R": "S", "O": "S",
    "SA": "S", "SK": "S", "SL": "S", "SQ": "S", "SR": "S",
    "SE": "S", "SFC": "S",
    # Metallic / X-complex
    "M": "M", "X": "M", "E": "M", "P": "M", "XC": "M", "XE": "M",
    # Basaltic
    "V": "V",
}

# ---------------------------------------------------------------------------
# Meteorite-analog resource model (Cannon 2023, Lodders+ 2025)
# ---------------------------------------------------------------------------

# Water content (wt%) — CI: Lodders+ 2025; CM: Garenne+ 2014; others: negligible
_WATER_WT_PCT: dict[str, float] = {
    "C": 15.0,    # CI/CM average (range 4–20%)
    "S": 0.0,     # ordinary chondrites — negligible
    "M": 0.0,     # iron meteorites — none
    "V": 0.0,     # HED achondrites — negligible
    "U": 1.5,     # population-weighted estimate
}

# Bulk metal (Fe+Ni+Co) content (wt%)
# CI: Lodders+ 2025; H: Wasson & Kallemeyn 1988; Iron: standard reference
_METAL_WT_PCT: dict[str, float] = {
    "C": 19.7,    # CI: 18.5% Fe + 1.1% Ni + 0.05% Co
    "S": 28.9,    # H-chondrite: 27.1% Fe + 1.7% Ni + 0.08% Co
    "M": 98.6,    # Iron: 91% Fe + 7% Ni + 0.6% Co
    "V": 15.0,    # HED: lower total metal
    "U": 25.0,    # population average
}

# Total PGM+Au concentration (ppm)
# CI: Lodders+ 2025 Table 4 (sum Ru+Rh+Pd+Os+Ir+Pt+Au = 3.375 ppm)
# Iron: Cannon+ 2023 Table 2 (50th percentile = 40.78 ppm, excl. Au; add ~1 ppm Au)
# H-chondrite: scaled from CI by metal fraction ratio
_PRECIOUS_PPM: dict[str, float] = {
    "C": 3.4,     # CI: 3.225 PGM + 0.15 Au (Lodders+ 2025)
    "S": 4.5,     # H-chondrite: higher metal fraction concentrates PGMs slightly
    "M": 42.0,    # Iron meteorite: 40.78 PGM + ~1 Au (Cannon+ 2023, 50th %ile)
    "V": 0.5,     # HED: extremely low PGM grades
    "U": 5.0,     # population estimate
}

# Economic parameters for value calculation
_WATER_PRICE_PER_KG = 500.0        # $/kg in cislunar space (propellant)
_WATER_EXTRACTION_YIELD = 0.60     # 60% yield for thermal extraction
_METAL_PRICE_PER_KG = 50.0         # $/kg in orbit (construction material)
_METAL_EXTRACTION_YIELD = 0.50     # 50% yield for magnetic/thermal separation
_PRECIOUS_PRICE_PER_KG = 35_000.0  # $/kg average PGM+Au (Earth-return spot)
_PRECIOUS_EXTRACTION_YIELD = 0.30  # 30% yield (refining in space is hard)

# Albedo thresholds for inference when taxonomy is unavailable
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


def resource_value_per_kg(composition_class: str) -> float:
    """
    Total estimated resource value per kg of raw asteroid material.

    Sum of water + bulk metals + precious metals, each adjusted for
    extraction yield and in-space vs Earth-return pricing.
    """
    c = composition_class if composition_class in _WATER_WT_PCT else "U"

    water_val = (_WATER_WT_PCT[c] / 100.0) * _WATER_EXTRACTION_YIELD * _WATER_PRICE_PER_KG
    metal_val = (_METAL_WT_PCT[c] / 100.0) * _METAL_EXTRACTION_YIELD * _METAL_PRICE_PER_KG
    precious_val = (
        _PRECIOUS_PPM[c] / 1e6
    ) * _PRECIOUS_EXTRACTION_YIELD * _PRECIOUS_PRICE_PER_KG

    return round(water_val + metal_val + precious_val, 2)


def resource_breakdown(composition_class: str) -> dict[str, float]:
    """
    Detailed resource value breakdown per kg for a composition class.

    Returns dict with water_usd, metals_usd, precious_usd, total_usd.
    """
    c = composition_class if composition_class in _WATER_WT_PCT else "U"

    water = (_WATER_WT_PCT[c] / 100.0) * _WATER_EXTRACTION_YIELD * _WATER_PRICE_PER_KG
    metals = (_METAL_WT_PCT[c] / 100.0) * _METAL_EXTRACTION_YIELD * _METAL_PRICE_PER_KG
    precious = (_PRECIOUS_PPM[c] / 1e6) * _PRECIOUS_EXTRACTION_YIELD * _PRECIOUS_PRICE_PER_KG

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
      - ``composition_class`` — C/S/M/V/U
      - ``composition_source`` — "taxonomy", "albedo", or "none"
      - ``resource_value_usd_per_kg`` — total $/kg (water + metals + precious)
      - ``water_value_usd_per_kg`` — water contribution to value
      - ``metals_value_usd_per_kg`` — bulk metals contribution
      - ``precious_value_usd_per_kg`` — PGM+Au contribution

    Classification priority: taxonomy first, albedo fallback, else unknown.
    """
    result = df.copy()
    n = len(df)
    comp_class = np.full(n, "U", dtype=object)
    comp_source = np.full(n, "none", dtype=object)

    # Layer 1: taxonomy (highest confidence)
    if "taxonomy" in df.columns:
        tax_vals = df["taxonomy"].values
        has_tax = pd.notna(tax_vals)
        if has_tax.any():
            mapped = np.array([classify_taxonomy(str(v)) for v in tax_vals[has_tax]])
            found = mapped != "U"
            positions = np.where(has_tax)[0][found]
            comp_class[positions] = mapped[found]
            comp_source[positions] = "taxonomy"

    # Layer 2: spectral_type fallback
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

    # Layer 3: albedo fallback
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

    # Compute per-resource value breakdown
    breakdowns = [resource_breakdown(c) for c in comp_class]
    result["resource_value_usd_per_kg"] = [b["total_usd_per_kg"] for b in breakdowns]
    result["water_value_usd_per_kg"] = [b["water_usd_per_kg"] for b in breakdowns]
    result["metals_value_usd_per_kg"] = [b["metals_usd_per_kg"] for b in breakdowns]
    result["precious_value_usd_per_kg"] = [b["precious_usd_per_kg"] for b in breakdowns]

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
    sources = result["composition_source"].value_counts().to_dict()

    # Show resource value summary per class
    for cls in ("C", "S", "M", "V", "U"):
        bd = resource_breakdown(cls)
        logger.info(
            "  %s: $%.2f/kg (water=$%.2f, metals=$%.2f, precious=$%.4f)",
            cls, bd["total_usd_per_kg"], bd["water_usd_per_kg"],
            bd["metals_usd_per_kg"], bd["precious_usd_per_kg"],
        )

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_composition_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — classes: %s | sources: %s | %.1fs",
        output_path.name, counts, sources,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
