from __future__ import annotations

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.overlays import (
    MEASURED_DENSITY,
    RADAR_ALBEDO,
    apply_overlays,
)


def _sample_df() -> pd.DataFrame:
    """DataFrame with prob columns and known overlay targets."""
    return pd.DataFrame({
        "spkid": [20000016, 20000001, 20101955, 20000999],
        "name": ["16 Psyche", "1 Ceres", "101955 Bennu", "999 Random"],
        "prob_C": [0.05, 0.90, 0.30, 0.25],
        "prob_S": [0.10, 0.05, 0.20, 0.25],
        "prob_M": [0.80, 0.02, 0.10, 0.25],
        "prob_V": [0.05, 0.03, 0.40, 0.25],
        "composition_class": ["M", "C", "V", "C"],
        "composition_confidence": [0.5, 0.8, 0.3, 0.0],
    })


class TestApplyOverlays:
    def test_adds_overlay_columns(self) -> None:
        result = apply_overlays(_sample_df())
        assert "radar_albedo" in result.columns
        assert "measured_density_kg_m3" in result.columns
        assert "overlay_source" in result.columns

    def test_psyche_gets_metallic_boost(self) -> None:
        result = apply_overlays(_sample_df())
        psyche = result[result["spkid"] == 20000016].iloc[0]
        # 16 Psyche has radar albedo 0.37 AND density 3780 → strong M
        assert psyche["prob_M"] > 0.75
        assert psyche["composition_class"] == "M"
        assert "radar" in str(psyche["overlay_source"])

    def test_bennu_gets_carbonaceous_boost(self) -> None:
        result = apply_overlays(_sample_df())
        bennu = result[result["spkid"] == 20101955].iloc[0]
        # Bennu has density 1260 kg/m³ → C-type
        assert bennu["prob_C"] > 0.50
        assert bennu["composition_class"] == "C"
        assert "density" in str(bennu["overlay_source"])

    def test_unmatched_unchanged(self) -> None:
        result = apply_overlays(_sample_df())
        random = result[result["spkid"] == 20000999].iloc[0]
        assert random["prob_C"] == pytest.approx(0.25)
        assert pd.isna(random["overlay_source"])

    def test_preserves_row_count(self) -> None:
        df = _sample_df()
        assert len(apply_overlays(df)) == len(df)

    def test_does_not_mutate_input(self) -> None:
        df = _sample_df()
        _ = apply_overlays(df)
        assert "radar_albedo" not in df.columns

    def test_probs_still_sum_to_one(self) -> None:
        result = apply_overlays(_sample_df())
        for _, row in result.iterrows():
            total = row["prob_C"] + row["prob_S"] + row["prob_M"] + row["prob_V"]
            assert abs(total - 1.0) < 0.01


class TestOverlayData:
    def test_radar_entries_exist(self) -> None:
        assert len(RADAR_ALBEDO) >= 10

    def test_density_entries_exist(self) -> None:
        assert len(MEASURED_DENSITY) >= 10

    def test_psyche_in_both(self) -> None:
        assert 20000016 in RADAR_ALBEDO
        assert 20000016 in MEASURED_DENSITY
