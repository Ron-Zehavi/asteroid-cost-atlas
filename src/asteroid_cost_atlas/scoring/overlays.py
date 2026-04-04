"""
High-confidence composition overlays for well-studied asteroids.

Provides curated lookup tables from radar albedo and measured density.
These cover only ~40 asteroids but with very high confidence.

Sources
-------
  Shepard et al. (2010, 2015): Radar albedo for M/X-type asteroids
  Carry (2012): Density compilation from binary systems + spacecraft
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CLASSES = ["C", "S", "M", "V"]

# Radar albedo: > 0.25 = metallic, < 0.10 = not metallic
RADAR_ALBEDO: dict[int, float] = {
    20000016: 0.37,   # 16 Psyche
    20000021: 0.36,   # 21 Lutetia
    20000022: 0.28,   # 22 Kalliope
    20000097: 0.32,   # 97 Klotho
    20000110: 0.28,   # 110 Lydia
    20000129: 0.26,   # 129 Antigone
    20000135: 0.30,   # 135 Hertha
    20000216: 0.43,   # 216 Kleopatra
    20000516: 0.25,   # 516 Amherstia
    20000758: 0.29,   # 758 Mancunia
}

# Measured density: > 3500 = metallic, < 1500 = porous carbonaceous
MEASURED_DENSITY: dict[int, float] = {
    20000001: 2162.0,   # 1 Ceres (Dawn)
    20000004: 3456.0,   # 4 Vesta (Dawn)
    20000016: 3780.0,   # 16 Psyche
    20000021: 3400.0,   # 21 Lutetia (Rosetta)
    20000216: 4270.0,   # 216 Kleopatra
    20000243: 2670.0,   # 243 Ida (Galileo)
    20000433: 2670.0,   # 433 Eros (NEAR)
    20025143: 1900.0,   # 25143 Itokawa (Hayabusa)
    20101955: 1260.0,   # 101955 Bennu (OSIRIS-REx)
    20162173: 1190.0,   # 162173 Ryugu (Hayabusa2)
}


def _set_probs(
    prob_c: float, prob_s: float, prob_m: float, prob_v: float,
    boost_class: str, target: float,
) -> tuple[float, float, float, float]:
    """Boost one class and renormalize."""
    probs = {"C": prob_c, "S": prob_s, "M": prob_m, "V": prob_v}
    probs[boost_class] = target
    remaining = 1.0 - target
    others = sum(v for k, v in probs.items() if k != boost_class)
    if others > 0:
        for k in probs:
            if k != boost_class:
                probs[k] = probs[k] / others * remaining
    else:
        for k in probs:
            if k != boost_class:
                probs[k] = remaining / 3
    return probs["C"], probs["S"], probs["M"], probs["V"]


def apply_overlays(df: pd.DataFrame) -> pd.DataFrame:
    """Apply high-confidence overlays. Modifies prob_* and confidence."""
    result = df.copy()
    n = len(df)

    result["radar_albedo"] = np.nan
    result["measured_density_kg_m3"] = np.nan
    result["overlay_source"] = pd.array([pd.NA] * n, dtype="string")

    if "spkid" not in df.columns or "prob_M" not in df.columns:
        return result

    # Build spkid index for fast lookup
    spkid_to_idx: dict[int, int] = {}
    for i, sid in enumerate(df["spkid"].values):
        if not np.isnan(sid):
            spkid_to_idx[int(sid)] = i

    adjustments = 0

    # Radar albedo overlays
    for sid, ra in RADAR_ALBEDO.items():
        if sid not in spkid_to_idx:
            continue
        i = spkid_to_idx[sid]
        result.loc[result.index[i], "radar_albedo"] = ra
        if ra > 0.25:
            _apply_boost(result, i, "M", 0.85)
            result.loc[result.index[i], "overlay_source"] = "radar"
            adjustments += 1

    # Density overlays
    for sid, density in MEASURED_DENSITY.items():
        if sid not in spkid_to_idx:
            continue
        i = spkid_to_idx[sid]
        result.loc[result.index[i], "measured_density_kg_m3"] = density
        if density > 3500:
            _apply_boost(result, i, "M", 0.80)
            existing = result.loc[result.index[i], "overlay_source"]
            src = "density" if pd.isna(existing) else f"{existing}+density"
            result.loc[result.index[i], "overlay_source"] = src
            adjustments += 1
        elif density < 1500:
            _apply_boost(result, i, "C", 0.75)
            existing = result.loc[result.index[i], "overlay_source"]
            src = "density" if pd.isna(existing) else f"{existing}+density"
            result.loc[result.index[i], "overlay_source"] = src
            adjustments += 1

    logger.info(
        "Overlays: %d radar, %d density entries, %d probability adjustments",
        len(RADAR_ALBEDO), len(MEASURED_DENSITY), adjustments,
    )

    return result


def _apply_boost(df: pd.DataFrame, row_pos: int, cls: str, target: float) -> None:
    """Boost class probability at row_pos and update confidence/class."""
    idx = df.index[row_pos]
    pc = float(df.loc[idx, "prob_C"])
    ps = float(df.loc[idx, "prob_S"])
    pm = float(df.loc[idx, "prob_M"])
    pv = float(df.loc[idx, "prob_V"])

    pc, ps, pm, pv = _set_probs(pc, ps, pm, pv, cls, target)
    df.loc[idx, "prob_C"] = pc
    df.loc[idx, "prob_S"] = ps
    df.loc[idx, "prob_M"] = pm
    df.loc[idx, "prob_V"] = pv

    # Update confidence
    probs = [pc, ps, pm, pv]
    max_ent = math.log(4)
    entropy = -sum(p * math.log(p) for p in probs if p > 1e-12)
    df.loc[idx, "composition_confidence"] = round(1.0 - entropy / max_ent, 4)

    # Update argmax class
    best = CLASSES[int(np.argmax(probs))]
    df.loc[idx, "composition_class"] = best
