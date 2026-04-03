from __future__ import annotations

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.composition import (
    add_composition_features,
    classify_albedo,
    classify_taxonomy,
    composition_confidence,
    infer_class_probabilities,
    resource_breakdown,
    resource_value_per_kg,
)


class TestClassifyTaxonomy:
    def test_c_type(self) -> None:
        for t in ("C", "B", "F", "G", "D", "T", "CB", "CG"):
            assert classify_taxonomy(t) == "C"

    def test_s_type(self) -> None:
        for t in ("S", "K", "L", "A", "Q", "R", "O", "SA", "SK"):
            assert classify_taxonomy(t) == "S"

    def test_m_type(self) -> None:
        for t in ("M", "X", "E", "P", "XC", "XE"):
            assert classify_taxonomy(t) == "M"

    def test_v_type(self) -> None:
        assert classify_taxonomy("V") == "V"

    def test_strips_asterisk(self) -> None:
        assert classify_taxonomy("S*") == "S"
        assert classify_taxonomy("C*") == "C"

    def test_unknown_returns_u(self) -> None:
        assert classify_taxonomy("ZZZ") == "U"
        assert classify_taxonomy("") == "U"
        assert classify_taxonomy(None) == "U"

    def test_case_insensitive(self) -> None:
        assert classify_taxonomy("c") == "C"
        assert classify_taxonomy("s*") == "S"


class TestClassifyAlbedo:
    def test_low_albedo_is_c(self) -> None:
        assert classify_albedo(0.05) == "C"

    def test_mid_albedo_is_s(self) -> None:
        assert classify_albedo(0.15) == "S"
        assert classify_albedo(0.25) == "S"

    def test_high_albedo_is_v(self) -> None:
        assert classify_albedo(0.40) == "V"

    def test_invalid_returns_u(self) -> None:
        assert classify_albedo(0.0) == "U"
        assert classify_albedo(-0.1) == "U"
        assert classify_albedo(float("nan")) == "U"
        assert classify_albedo(float("inf")) == "U"


class TestInferClassProbabilities:
    def test_probs_sum_to_one(self) -> None:
        probs = infer_class_probabilities()
        assert abs(sum(probs.values()) - 1.0) < 1e-6

    def test_taxonomy_dominates(self) -> None:
        probs = infer_class_probabilities(taxonomy="C")
        assert probs["C"] > 0.85
        assert probs["S"] < 0.10

    def test_spectral_type_strong(self) -> None:
        probs = infer_class_probabilities(spectral_type="M")
        assert probs["M"] > 0.20  # lifted from low prior=0.05

    def test_albedo_shifts_m_probability(self) -> None:
        """Albedo ~0.14 should give nonzero M probability (unlike deterministic)."""
        probs = infer_class_probabilities(albedo=0.14)
        assert probs["M"] > 0.05  # key improvement over old system

    def test_low_albedo_favors_c(self) -> None:
        probs = infer_class_probabilities(albedo=0.05)
        assert probs["C"] > probs["S"]

    def test_high_albedo_favors_v(self) -> None:
        probs = infer_class_probabilities(albedo=0.40)
        # V has low prior (0.05) but high albedo gives strong likelihood
        assert probs["V"] > 0.05  # meaningfully above prior

    def test_no_evidence_returns_prior(self) -> None:
        probs = infer_class_probabilities()
        # Should be close to prior: C=0.35, S=0.45, M=0.05, V=0.05
        assert probs["S"] > probs["C"] > probs["M"]

    def test_sdss_colors_inform(self) -> None:
        probs = infer_class_probabilities(color_gr=0.42, color_ri=0.04)
        assert probs["C"] > 0.30  # C-type centroids

    def test_joint_albedo_and_colors(self) -> None:
        """Joint evidence should be more certain than either alone."""
        alb_only = infer_class_probabilities(albedo=0.06)
        joint = infer_class_probabilities(albedo=0.06, color_gr=0.42, color_ri=0.04)
        assert composition_confidence(joint) >= composition_confidence(alb_only)


class TestCompositionConfidence:
    def test_certain(self) -> None:
        probs = {"C": 0.99, "S": 0.003, "M": 0.003, "V": 0.004}
        assert composition_confidence(probs) > 0.8

    def test_uniform_low(self) -> None:
        probs = {"C": 0.25, "S": 0.25, "M": 0.25, "V": 0.25}
        assert composition_confidence(probs) < 0.01

    def test_range(self) -> None:
        for tax in ("C", "S", "M", "V", None):
            probs = infer_class_probabilities(taxonomy=tax)
            c = composition_confidence(probs)
            assert 0.0 <= c <= 1.0


class TestResourceValuePerKg:
    def test_c_type_dominated_by_water(self) -> None:
        bd = resource_breakdown("C")
        assert bd["water_usd_per_kg"] > bd["metals_usd_per_kg"]
        assert bd["water_usd_per_kg"] > bd["precious_usd_per_kg"]

    def test_m_type_dominated_by_metals(self) -> None:
        bd = resource_breakdown("M")
        assert bd["metals_usd_per_kg"] > bd["water_usd_per_kg"]
        assert bd["metals_usd_per_kg"] > bd["precious_usd_per_kg"]

    def test_c_type_most_valuable_per_kg(self) -> None:
        assert resource_value_per_kg("C") > resource_value_per_kg("S")
        assert resource_value_per_kg("C") > resource_value_per_kg("M")

    def test_m_type_more_valuable_than_s(self) -> None:
        assert resource_value_per_kg("M") > resource_value_per_kg("S")

    def test_v_type_lowest(self) -> None:
        assert resource_value_per_kg("V") < resource_value_per_kg("S")

    def test_all_values_positive(self) -> None:
        for cls in ("C", "S", "M", "V", "U"):
            assert resource_value_per_kg(cls) > 0

    def test_unknown_gets_intermediate_value(self) -> None:
        u_val = resource_value_per_kg("U")
        assert u_val > resource_value_per_kg("V")
        assert u_val < resource_value_per_kg("C")

    def test_breakdown_sums_to_total(self) -> None:
        for cls in ("C", "S", "M", "V", "U"):
            bd = resource_breakdown(cls)
            expected = bd["water_usd_per_kg"] + bd["metals_usd_per_kg"] + bd["precious_usd_per_kg"]
            assert abs(bd["total_usd_per_kg"] - expected) < 0.01


class TestAddCompositionFeatures:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [1, 2, 3, 4, 5],
                "taxonomy": ["C", "S*", None, None, None],
                "spectral_type": [None, None, "M", None, None],
                "albedo": [0.09, 0.25, 0.15, 0.04, None],
            }
        )

    def test_has_probability_columns(self) -> None:
        result = add_composition_features(self._sample_df())
        for col in ("prob_C", "prob_S", "prob_M", "prob_V", "composition_confidence"):
            assert col in result.columns

    def test_probs_sum_to_one(self) -> None:
        result = add_composition_features(self._sample_df())
        row_sums = result[["prob_C", "prob_S", "prob_M", "prob_V"]].sum(axis=1)
        for s in row_sums:
            assert abs(s - 1.0) < 1e-6

    def test_confidence_in_range(self) -> None:
        result = add_composition_features(self._sample_df())
        assert (result["composition_confidence"] >= 0).all()
        assert (result["composition_confidence"] <= 1).all()

    def test_taxonomy_gives_high_confidence(self) -> None:
        result = add_composition_features(self._sample_df())
        # Row 0 has taxonomy="C" — should be very confident
        assert result.loc[0, "composition_confidence"] > 0.7

    def test_no_evidence_gives_low_confidence(self) -> None:
        result = add_composition_features(self._sample_df())
        # Row 4 has no taxonomy, spectral, or albedo — prior only
        assert result.loc[4, "composition_confidence"] < 0.4

    def test_backward_compatible_columns(self) -> None:
        result = add_composition_features(self._sample_df())
        for col in (
            "composition_class", "composition_source", "resource_value_usd_per_kg",
            "water_value_usd_per_kg", "metals_value_usd_per_kg", "precious_value_usd_per_kg",
            "specimen_value_per_kg",
        ):
            assert col in result.columns

    def test_taxonomy_takes_priority(self) -> None:
        result = add_composition_features(self._sample_df())
        assert result.loc[0, "composition_class"] == "C"
        assert result.loc[0, "composition_source"] == "taxonomy"

    def test_spectral_type_recognized(self) -> None:
        result = add_composition_features(self._sample_df())
        assert result.loc[2, "composition_class"] == "M"

    def test_low_albedo_favors_c(self) -> None:
        result = add_composition_features(self._sample_df())
        # Row 3: albedo=0.04, no taxonomy → should be C
        assert result.loc[3, "composition_class"] == "C"

    def test_does_not_mutate_input(self) -> None:
        df = self._sample_df()
        _ = add_composition_features(df)
        assert "composition_class" not in df.columns

    def test_preserves_row_count(self) -> None:
        df = self._sample_df()
        assert len(add_composition_features(df)) == len(df)

    def test_ppm_low_high_columns(self) -> None:
        result = add_composition_features(self._sample_df())
        assert "platinum_ppm" in result.columns
        assert "platinum_ppm_low" in result.columns
        assert "platinum_ppm_high" in result.columns

    def test_ppm_low_le_mid_le_high(self) -> None:
        result = add_composition_features(self._sample_df())
        for _, row in result.iterrows():
            assert row["platinum_ppm_low"] <= row["platinum_ppm"] + 1e-6
            assert row["platinum_ppm"] <= row["platinum_ppm_high"] + 1e-6

    def test_prob_weighted_values_differ_from_hard(self) -> None:
        """Prob-weighted resource values should differ from hard-class values
        for asteroids with ambiguous classification."""
        df = pd.DataFrame({
            "spkid": [1],
            "albedo": [0.14],  # ambiguous: S or M
        })
        result = add_composition_features(df)
        hard_class = result.loc[0, "composition_class"]
        hard_value = resource_value_per_kg(hard_class)
        prob_value = result.loc[0, "resource_value_usd_per_kg"]
        # Prob-weighted should differ because it mixes S and M contributions
        assert prob_value != pytest.approx(hard_value, rel=0.01)

    def test_m_type_probability_nonzero_for_moderate_albedo(self) -> None:
        """Key improvement: moderate albedo should give nonzero M probability."""
        df = pd.DataFrame({
            "spkid": [1],
            "albedo": [0.14],
        })
        result = add_composition_features(df)
        assert result.loc[0, "prob_M"] > 0.05
