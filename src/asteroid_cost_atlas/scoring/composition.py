"""
Composition proxy scoring.

Infers asteroid resource class from taxonomy and/or albedo, then assigns
estimated resource value per kg based on published meteorite compositions.

Composition classes
-------------------
  C  — carbonaceous: water ~10-20%, organics, carbon (C, B, F, G, D, T types)
  S  — silicaceous: iron/nickel ~25%, trace PGMs (S, K, L, A, Q, R, O types)
  M  — metallic: iron/nickel ~80%, PGMs ~50 ppm (M, X types)
  V  — basaltic: pyroxene/feldspar, low resource value (V type)
  U  — unknown: no taxonomy or albedo available

Classification priority:
  1. LCDB/SBDB taxonomy → direct mapping
  2. Albedo range → probabilistic inference
  3. Neither available → "U" (unknown)

Resource value model
--------------------
Values represent estimated $/kg of raw asteroid material based on
the dominant extractable resource for each class:

  C-type: $500/kg  — water as in-space propellant (H₂+O₂ electrolysis)
  S-type: $  1/kg  — silicates + trace PGMs, low extraction yield
  M-type: $ 50/kg  — iron/nickel bulk + PGMs (~50 ppm at ~$30k/kg)
  V-type: $  0/kg  — basaltic, no known high-value extractables
  U-type: $ 10/kg  — population-weighted average

These are order-of-magnitude estimates for in-space utilisation economics,
not Earth-return commodity values. The dominant factor is water: C-types
are the most valuable per-kg because water is the scarcest resource in
space (propellant, life support, radiation shielding).

References: Lewis (1996) "Mining the Sky"; Sonter (1997); Elvis (2012).
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

# Maps LCDB/SBDB taxonomy codes to composition class.
# Asterisks and subclasses are stripped before lookup.
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

# Estimated resource value ($/kg of raw asteroid material)
_VALUE_PER_KG: dict[str, float] = {
    "C": 500.0,   # water as propellant
    "S": 1.0,     # silicates, trace PGMs
    "M": 50.0,    # iron/nickel + PGMs
    "V": 0.1,     # basaltic, minimal value
    "U": 10.0,    # unknown — population-weighted average
}

# Albedo thresholds for inference when taxonomy is unavailable
_ALBEDO_LOW = 0.10    # below → likely C-type
_ALBEDO_MID = 0.20    # below → ambiguous, default S
_ALBEDO_HIGH = 0.35   # above → likely V-type or E-type


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def classify_taxonomy(taxonomy: str | None) -> str:
    """Map a taxonomy string to a composition class (C/S/M/V/U)."""
    if taxonomy is None or not isinstance(taxonomy, str):
        return "U"
    # Strip asterisks, colons, trailing characters
    clean = taxonomy.strip().rstrip("*:").upper()
    if clean in _TAXONOMY_MAP:
        return _TAXONOMY_MAP[clean]
    # Try first character
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
        return "S"  # ambiguous region, default to most common
    if albedo < _ALBEDO_HIGH:
        return "S"
    return "V"


def resource_value_per_kg(composition_class: str) -> float:
    """Return estimated $/kg for a composition class."""
    return _VALUE_PER_KG.get(composition_class, _VALUE_PER_KG["U"])


# ---------------------------------------------------------------------------
# Vectorised DataFrame transformer
# ---------------------------------------------------------------------------


def add_composition_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add composition proxy columns to the asteroid DataFrame.

    Added columns:
      - ``composition_class`` — C/S/M/V/U
      - ``composition_source`` — "taxonomy", "albedo", or "none"
      - ``resource_value_usd_per_kg`` — estimated $/kg for the class

    Classification priority: taxonomy first, albedo fallback, else unknown.
    """
    result = df.copy()
    n = len(df)
    comp_class = np.full(n, "U", dtype=object)
    comp_source = np.full(n, "none", dtype=object)

    # Layer 1: taxonomy (highest confidence)
    if "taxonomy" in df.columns:
        has_tax = df["taxonomy"].notna()
        for idx in df.index[has_tax]:
            mapped = classify_taxonomy(str(df.loc[idx, "taxonomy"]))
            if mapped != "U":
                comp_class[idx] = mapped
                comp_source[idx] = "taxonomy"

    # Layer 2: spectral_type fallback
    if "spectral_type" in df.columns:
        still_unknown = comp_class == "U"
        has_spec = df["spectral_type"].notna() & still_unknown
        for idx in df.index[has_spec]:
            mapped = classify_taxonomy(str(df.loc[idx, "spectral_type"]))
            if mapped != "U":
                comp_class[idx] = mapped
                comp_source[idx] = "taxonomy"

    # Layer 3: albedo fallback
    if "albedo" in df.columns:
        still_unknown = comp_class == "U"
        has_albedo = df["albedo"].notna() & still_unknown
        for idx in df.index[has_albedo]:
            mapped = classify_albedo(float(df.loc[idx, "albedo"]))
            if mapped != "U":
                comp_class[idx] = mapped
                comp_source[idx] = "albedo"

    result["composition_class"] = comp_class
    result["composition_source"] = comp_source
    result["resource_value_usd_per_kg"] = [
        resource_value_per_kg(c) for c in comp_class
    ]

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

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_composition_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — classes: %s | sources: %s | %.1fs",
        output_path.name,
        counts,
        sources,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
