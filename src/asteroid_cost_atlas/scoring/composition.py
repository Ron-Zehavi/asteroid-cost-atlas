"""
Probabilistic composition inference with per-metal resource model.

Replaces deterministic class assignment with Bayesian inference over
four resource classes (C/S/M/V), producing probability distributions
and uncertainty-aware resource estimates.

Architecture
------------
  evidence layer  →  taxonomy / spectral / SDSS colors / albedo
  inference layer →  class probability vector (prob_C, prob_S, prob_M, prob_V)
  resource layer  →  probability-weighted water / bulk metal / PGM estimates
  output layer    →  mean, P10, P90 values + confidence score

Backward compatible: ``composition_class`` = argmax of probabilities.

Sources
-------
  Cannon+ (2023): PGM in iron meteorites, P10/P50/P90 distributions
  Lodders+ (2025): CI chondrite bulk chemistry
  Garenne+ (2014): CI/CM/CR water content
  Dunn+ (2010): H/L/LL chondrite metal fractions
  Mainzer+ (2011): WISE/NEOWISE albedo distributions by class
  Carvano+ (2010): joint SDSS+albedo taxonomy
  Burbine+ (2002): meteorite fall-frequency priors
  DeMeo & Carry (2013): probabilistic taxonomy framework
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
# Resource classes
# ---------------------------------------------------------------------------

CLASSES: list[str] = ["C", "S", "M", "V"]

# ---------------------------------------------------------------------------
# Taxonomy → composition class mapping (unchanged, used for likelihood)
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
# Bayesian inference parameters
# ---------------------------------------------------------------------------

# Prior: bias-corrected meteorite fall frequencies (Burbine+ 2002)
# Iron meteorites over-represented in falls (survive entry) → corrected down
CLASS_PRIOR: dict[str, float] = {"C": 0.35, "S": 0.45, "M": 0.05, "V": 0.05}
_PRIOR_LEFTOVER = 1.0 - sum(CLASS_PRIOR.values())  # remainder for normalization

# Albedo class-conditional distributions (Mainzer+ 2011, Gaussian approx)
# (mean, std_dev) for geometric albedo pV
_ALBEDO_DIST: dict[str, tuple[float, float]] = {
    "C": (0.06, 0.03),
    "S": (0.25, 0.08),
    "M": (0.14, 0.05),
    "V": (0.35, 0.10),
}

# SDSS color class centroids and spreads (from Carvano+ 2010, simplified)
# (g-r mean, g-r std, r-i mean, r-i std)
_SDSS_DIST: dict[str, tuple[float, float, float, float]] = {
    "C": (0.42, 0.06, 0.04, 0.04),
    "S": (0.55, 0.07, 0.13, 0.05),
    "M": (0.48, 0.06, 0.08, 0.04),
    "V": (0.40, 0.05, 0.16, 0.05),
}

# ---------------------------------------------------------------------------
# Per-metal concentration model: P10 / P50 / P90
# ---------------------------------------------------------------------------

METALS: list[str] = [
    "platinum", "palladium", "rhodium", "iridium", "osmium", "ruthenium", "gold",
]

METAL_SPOT_PRICE: dict[str, float] = {
    "platinum":   63_300.0,
    "palladium":  47_870.0,
    "rhodium":   299_000.0,
    "iridium":   254_000.0,
    "osmium":     12_860.0,
    "ruthenium":  56_260.0,
    "gold":      150_740.0,
}

# PGM concentrations (ppm) per class: {p10, p50, p90}
# M-type: Cannon+ (2023) Table 2, iron meteorite distributions
# C-type: Lodders+ (2025) CI chondrite ±20% measurement uncertainty
# S-type: interpolated from CI × H-chondrite metal fraction (Dunn+ 2010)
# V-type: HED achondrite literature, very low PGM
METAL_PPM_RANGES: dict[str, dict[str, dict[str, float]]] = {
    "C": {
        "platinum":  {"p10": 0.70, "p50": 0.90, "p90": 1.15},
        "palladium": {"p10": 0.44, "p50": 0.56, "p90": 0.72},
        "rhodium":   {"p10": 0.10, "p50": 0.13, "p90": 0.17},
        "iridium":   {"p10": 0.36, "p50": 0.46, "p90": 0.59},
        "osmium":    {"p10": 0.38, "p50": 0.49, "p90": 0.63},
        "ruthenium": {"p10": 0.53, "p50": 0.68, "p90": 0.87},
        "gold":      {"p10": 0.12, "p50": 0.15, "p90": 0.19},
    },
    "S": {
        "platinum":  {"p10": 0.80, "p50": 1.20, "p90": 1.80},
        "palladium": {"p10": 0.50, "p50": 0.75, "p90": 1.12},
        "rhodium":   {"p10": 0.11, "p50": 0.17, "p90": 0.26},
        "iridium":   {"p10": 0.41, "p50": 0.61, "p90": 0.92},
        "osmium":    {"p10": 0.43, "p50": 0.65, "p90": 0.98},
        "ruthenium": {"p10": 0.60, "p50": 0.90, "p90": 1.35},
        "gold":      {"p10": 0.13, "p50": 0.20, "p90": 0.30},
    },
    "M": {
        "platinum":  {"p10": 3.0,  "p50": 15.0, "p90": 45.0},
        "palladium": {"p10": 1.6,  "p50": 8.0,  "p90": 24.0},
        "rhodium":   {"p10": 0.4,  "p50": 2.0,  "p90": 6.0},
        "iridium":   {"p10": 1.0,  "p50": 5.0,  "p90": 15.0},
        "osmium":    {"p10": 1.0,  "p50": 5.0,  "p90": 15.0},
        "ruthenium": {"p10": 1.2,  "p50": 6.0,  "p90": 18.0},
        "gold":      {"p10": 0.2,  "p50": 1.0,  "p90": 3.0},
    },
    "V": {
        "platinum":  {"p10": 0.06, "p50": 0.10, "p90": 0.16},
        "palladium": {"p10": 0.04, "p50": 0.06, "p90": 0.10},
        "rhodium":   {"p10": 0.006, "p50": 0.01, "p90": 0.016},
        "iridium":   {"p10": 0.03, "p50": 0.05, "p90": 0.08},
        "osmium":    {"p10": 0.03, "p50": 0.05, "p90": 0.08},
        "ruthenium": {"p10": 0.04, "p50": 0.07, "p90": 0.11},
        "gold":      {"p10": 0.01, "p50": 0.02, "p90": 0.03},
    },
}

# Backward-compatible single-value PPM (P50 values)
METAL_PPM: dict[str, dict[str, float]] = {
    cls: {m: METAL_PPM_RANGES[cls][m]["p50"] for m in METALS}
    for cls in CLASSES
}
# U-class uses prior-weighted average of P50s
METAL_PPM["U"] = {
    m: sum(CLASS_PRIOR[c] * METAL_PPM[c][m] for c in CLASSES)
    / sum(CLASS_PRIOR.values())
    for m in METALS
}

PRECIOUS_EXTRACTION_YIELD = 0.30

# Bulk resource parameters (water, metals) — separate from PGM
_WATER_WT_PCT: dict[str, float] = {"C": 15.0, "S": 0.0, "M": 0.0, "V": 0.0}
_METAL_WT_PCT: dict[str, float] = {"C": 19.7, "S": 28.9, "M": 98.6, "V": 15.0}
_WATER_PRICE_PER_KG = 500.0
_WATER_EXTRACTION_YIELD = 0.60
_METAL_PRICE_PER_KG = 50.0
_METAL_EXTRACTION_YIELD = 0.50


# ---------------------------------------------------------------------------
# Scalar helpers (backward compatible)
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
    """Infer composition class from albedo alone (deterministic fallback)."""
    if not math.isfinite(albedo) or albedo <= 0:
        return "U"
    if albedo < 0.10:
        return "C"
    if albedo < 0.35:
        return "S"
    return "V"


def specimen_value_per_kg(composition_class: str) -> float:
    """Value of 1 kg of refined precious metal concentrate."""
    c = composition_class if composition_class in METAL_PPM else "U"
    ppm = METAL_PPM[c]
    total_ppm = sum(ppm.values())
    if total_ppm == 0:
        return 0.0
    weighted_price = sum(
        (ppm[m] / total_ppm) * METAL_SPOT_PRICE[m] for m in METALS
    )
    return round(weighted_price, 2)


def resource_value_per_kg(composition_class: str) -> float:
    """Total commodity value per kg of raw asteroid material."""
    c = composition_class if composition_class in METAL_PPM else "U"
    wt_water = _WATER_WT_PCT.get(c, 1.5)
    wt_metal = _METAL_WT_PCT.get(c, 25.0)
    water = (wt_water / 100.0) * _WATER_EXTRACTION_YIELD * _WATER_PRICE_PER_KG
    metals = (wt_metal / 100.0) * _METAL_EXTRACTION_YIELD * _METAL_PRICE_PER_KG
    ppm = METAL_PPM.get(c, METAL_PPM["U"])
    precious = sum(
        (ppm[m] / 1e6) * PRECIOUS_EXTRACTION_YIELD * METAL_SPOT_PRICE[m]
        for m in METALS
    )
    return round(water + metals + precious, 2)


def resource_breakdown(composition_class: str) -> dict[str, float]:
    """Detailed commodity value breakdown per kg."""
    c = composition_class if composition_class in METAL_PPM else "U"
    wt_water = _WATER_WT_PCT.get(c, 1.5)
    wt_metal = _METAL_WT_PCT.get(c, 25.0)
    water = (wt_water / 100.0) * _WATER_EXTRACTION_YIELD * _WATER_PRICE_PER_KG
    metals = (wt_metal / 100.0) * _METAL_EXTRACTION_YIELD * _METAL_PRICE_PER_KG
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
# Bayesian inference engine
# ---------------------------------------------------------------------------


def _gaussian_pdf(x: float, mu: float, sigma: float) -> float:
    """Unnormalized Gaussian PDF (we only need relative likelihoods)."""
    if sigma <= 0:
        return 1.0
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def infer_class_probabilities(
    taxonomy: str | None = None,
    spectral_type: str | None = None,
    albedo: float | None = None,
    color_gr: float | None = None,
    color_ri: float | None = None,
) -> dict[str, float]:
    """
    Compute posterior class probabilities from available evidence.

    Returns dict with keys C, S, M, V summing to 1.0.
    Uses Bayesian update: P(class|evidence) ~ P(class) × L(evidence|class).
    """
    # Start with prior
    posterior = {c: CLASS_PRIOR[c] for c in CLASSES}

    # Taxonomy likelihood (strong signal)
    if taxonomy is not None and isinstance(taxonomy, str):
        tax_class = classify_taxonomy(taxonomy)
        if tax_class != "U":
            for c in CLASSES:
                posterior[c] *= 0.95 if c == tax_class else 0.017

    # Spectral type likelihood (strong but slightly weaker)
    if spectral_type is not None and isinstance(spectral_type, str):
        spec_class = classify_taxonomy(spectral_type)
        if spec_class != "U":
            for c in CLASSES:
                posterior[c] *= 0.85 if c == spec_class else 0.05

    # Albedo likelihood (Gaussian per class)
    if albedo is not None and math.isfinite(albedo) and albedo > 0:
        for c in CLASSES:
            mu, sigma = _ALBEDO_DIST[c]
            posterior[c] *= _gaussian_pdf(albedo, mu, sigma)

    # SDSS color likelihood (bivariate Gaussian per class)
    if (color_gr is not None and color_ri is not None
            and math.isfinite(color_gr) and math.isfinite(color_ri)):
        for c in CLASSES:
            gr_mu, gr_sig, ri_mu, ri_sig = _SDSS_DIST[c]
            l_gr = _gaussian_pdf(color_gr, gr_mu, gr_sig)
            l_ri = _gaussian_pdf(color_ri, ri_mu, ri_sig)
            posterior[c] *= l_gr * l_ri

    # Normalize
    total = sum(posterior.values())
    if total > 0:
        for c in CLASSES:
            posterior[c] /= total
    else:
        # Fallback to prior
        total_p = sum(CLASS_PRIOR.values())
        for c in CLASSES:
            posterior[c] = CLASS_PRIOR[c] / total_p

    return posterior


def composition_confidence(probs: dict[str, float]) -> float:
    """
    Confidence score in [0, 1] based on entropy of the probability distribution.

    1.0 = one class has all probability (certain).
    0.0 = uniform distribution (no information).
    """
    max_entropy = math.log(len(CLASSES))
    if max_entropy == 0:
        return 1.0
    entropy = -sum(
        p * math.log(p) for p in probs.values() if p > 1e-12
    )
    return round(1.0 - entropy / max_entropy, 4)


def _dominant_source(
    taxonomy: str | None,
    spectral_type: str | None,
    albedo: float | None,
    color_gr: float | None,
    color_ri: float | None,
) -> str:
    """Identify the highest-weight evidence source for provenance tracking."""
    if taxonomy is not None and isinstance(taxonomy, str) and classify_taxonomy(taxonomy) != "U":
        return "taxonomy"
    if (spectral_type is not None and isinstance(spectral_type, str)
            and classify_taxonomy(spectral_type) != "U"):
        return "spectral_type"
    if (color_gr is not None and color_ri is not None
            and math.isfinite(color_gr) and math.isfinite(color_ri)):
        return "sdss_colors"
    if albedo is not None and math.isfinite(albedo) and albedo > 0:
        return "albedo"
    return "prior_only"


# ---------------------------------------------------------------------------
# Vectorised DataFrame transformer
# ---------------------------------------------------------------------------


def add_composition_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add probabilistic composition columns to the asteroid DataFrame.

    New columns:
      - prob_C, prob_S, prob_M, prob_V (class probabilities)
      - composition_class (argmax, backward compatible)
      - composition_confidence (0=uniform, 1=certain)
      - composition_source (dominant evidence)
      - Probability-weighted resource values (water, metals, precious)
      - Per-metal ppm: expected (prob-weighted), low (P10), high (P90)
    """
    result = df.copy()
    n = len(df)

    # Extract evidence columns
    tax_vals = df["taxonomy"].values if "taxonomy" in df.columns else [None] * n
    spec_vals = df["spectral_type"].values if "spectral_type" in df.columns else [None] * n
    alb_vals = (
        df["albedo"].to_numpy(dtype=float, na_value=np.nan)
        if "albedo" in df.columns else np.full(n, np.nan)
    )
    gr_vals = (
        df["color_gr"].to_numpy(dtype=float, na_value=np.nan)
        if "color_gr" in df.columns else np.full(n, np.nan)
    )
    ri_vals = (
        df["color_ri"].to_numpy(dtype=float, na_value=np.nan)
        if "color_ri" in df.columns else np.full(n, np.nan)
    )

    # Compute per-asteroid probabilities
    prob_arr = np.zeros((n, 4))
    conf_arr = np.zeros(n)
    source_arr = np.empty(n, dtype=object)
    comp_class_arr = np.empty(n, dtype=object)

    for i in range(n):
        tax = str(tax_vals[i]) if pd.notna(tax_vals[i]) else None
        spec = str(spec_vals[i]) if pd.notna(spec_vals[i]) else None
        alb = float(alb_vals[i]) if np.isfinite(alb_vals[i]) else None
        gr = float(gr_vals[i]) if np.isfinite(gr_vals[i]) else None
        ri = float(ri_vals[i]) if np.isfinite(ri_vals[i]) else None

        probs = infer_class_probabilities(tax, spec, alb, gr, ri)
        prob_arr[i] = [probs[c] for c in CLASSES]
        conf_arr[i] = composition_confidence(probs)
        source_arr[i] = _dominant_source(tax, spec, alb, gr, ri)
        comp_class_arr[i] = CLASSES[int(np.argmax(prob_arr[i]))]

    result["prob_C"] = prob_arr[:, 0]
    result["prob_S"] = prob_arr[:, 1]
    result["prob_M"] = prob_arr[:, 2]
    result["prob_V"] = prob_arr[:, 3]
    result["composition_class"] = comp_class_arr
    result["composition_confidence"] = conf_arr
    result["composition_source"] = source_arr

    # Probability-weighted resource values
    water_per_kg = np.zeros(n)
    metals_per_kg = np.zeros(n)
    precious_per_kg = np.zeros(n)
    for j, c in enumerate(CLASSES):
        wt_water = _WATER_WT_PCT.get(c, 0.0)
        wt_metal = _METAL_WT_PCT.get(c, 0.0)
        w = (wt_water / 100.0) * _WATER_EXTRACTION_YIELD * _WATER_PRICE_PER_KG
        m = (wt_metal / 100.0) * _METAL_EXTRACTION_YIELD * _METAL_PRICE_PER_KG
        p = sum(
            (METAL_PPM[c][metal] / 1e6) * PRECIOUS_EXTRACTION_YIELD * METAL_SPOT_PRICE[metal]
            for metal in METALS
        )
        water_per_kg += prob_arr[:, j] * w
        metals_per_kg += prob_arr[:, j] * m
        precious_per_kg += prob_arr[:, j] * p

    result["water_value_usd_per_kg"] = np.round(water_per_kg, 4)
    result["metals_value_usd_per_kg"] = np.round(metals_per_kg, 4)
    result["precious_value_usd_per_kg"] = np.round(precious_per_kg, 4)
    result["resource_value_usd_per_kg"] = np.round(
        water_per_kg + metals_per_kg + precious_per_kg, 2,
    )

    # Specimen value (prob-weighted)
    specimen_vals = np.zeros(n)
    for j, c in enumerate(CLASSES):
        specimen_vals += prob_arr[:, j] * specimen_value_per_kg(c)
    result["specimen_value_per_kg"] = np.round(specimen_vals, 2)

    # Per-metal PPM: expected (prob-weighted P50), low (prob-weighted P10), high (prob-weighted P90)
    for metal in METALS:
        ppm_expected = np.zeros(n)
        ppm_low = np.zeros(n)
        ppm_high = np.zeros(n)
        for j, c in enumerate(CLASSES):
            ranges = METAL_PPM_RANGES[c][metal]
            ppm_expected += prob_arr[:, j] * ranges["p50"]
            ppm_low += prob_arr[:, j] * ranges["p10"]
            ppm_high += prob_arr[:, j] * ranges["p90"]
        result[f"{metal}_ppm"] = np.round(ppm_expected, 4)
        result[f"{metal}_ppm_low"] = np.round(ppm_low, 4)
        result[f"{metal}_ppm_high"] = np.round(ppm_high, 4)

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
    avg_conf = result["composition_confidence"].mean()

    for cls in CLASSES:
        sv = specimen_value_per_kg(cls)
        cv = resource_value_per_kg(cls)
        logger.info("  %s: specimen=$%.0f/kg, commodity=$%.2f/kg", cls, sv, cv)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_composition_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — classes: %s | avg_confidence: %.3f | %.1fs",
        output_path.name, counts, avg_conf,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
