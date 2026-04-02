from __future__ import annotations

import pandas as pd

from asteroid_cost_atlas.scoring.composition import (
    add_composition_features,
    classify_albedo,
    classify_taxonomy,
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
        # Water makes C-types the most valuable per kg
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

    def test_adds_six_columns(self) -> None:
        result = add_composition_features(self._sample_df())
        for col in (
            "composition_class", "composition_source", "resource_value_usd_per_kg",
            "water_value_usd_per_kg", "metals_value_usd_per_kg", "precious_value_usd_per_kg",
        ):
            assert col in result.columns

    def test_taxonomy_takes_priority(self) -> None:
        result = add_composition_features(self._sample_df())
        assert result.loc[0, "composition_class"] == "C"
        assert result.loc[0, "composition_source"] == "taxonomy"

    def test_spectral_type_fallback(self) -> None:
        result = add_composition_features(self._sample_df())
        assert result.loc[2, "composition_class"] == "M"
        assert result.loc[2, "composition_source"] == "taxonomy"

    def test_albedo_fallback(self) -> None:
        result = add_composition_features(self._sample_df())
        assert result.loc[3, "composition_class"] == "C"
        assert result.loc[3, "composition_source"] == "albedo"

    def test_unknown_when_nothing_available(self) -> None:
        result = add_composition_features(self._sample_df())
        assert result.loc[4, "composition_class"] == "U"
        assert result.loc[4, "composition_source"] == "none"

    def test_value_matches_class(self) -> None:
        result = add_composition_features(self._sample_df())
        for _, row in result.iterrows():
            assert row["resource_value_usd_per_kg"] == resource_value_per_kg(
                row["composition_class"]
            )

    def test_does_not_mutate_input(self) -> None:
        df = self._sample_df()
        _ = add_composition_features(df)
        assert "composition_class" not in df.columns

    def test_preserves_row_count(self) -> None:
        df = self._sample_df()
        assert len(add_composition_features(df)) == len(df)

    def test_water_value_zero_for_non_c(self) -> None:
        result = add_composition_features(self._sample_df())
        # Row 1 is S-type
        assert result.loc[1, "water_value_usd_per_kg"] == 0.0

    def test_sdss_colors_classify_unknown(self) -> None:
        """SDSS color indices should classify asteroids lacking taxonomy/spectral/albedo."""
        df = pd.DataFrame(
            {
                "spkid": [1, 2, 3],
                "taxonomy": [None, None, None],
                "spectral_type": [None, None, None],
                "albedo": [None, None, None],
                "color_gr": [0.40, 0.55, 0.40],
                "color_ri": [0.05, 0.12, 0.15],
            }
        )
        result = add_composition_features(df)
        assert result.loc[0, "composition_class"] == "C"
        assert result.loc[0, "composition_source"] == "sdss_colors"
        assert result.loc[1, "composition_class"] == "S"
        assert result.loc[1, "composition_source"] == "sdss_colors"
        assert result.loc[2, "composition_class"] == "V"
        assert result.loc[2, "composition_source"] == "sdss_colors"

    def test_taxonomy_overrides_sdss_colors(self) -> None:
        """Taxonomy should take priority over SDSS color indices."""
        df = pd.DataFrame(
            {
                "spkid": [1],
                "taxonomy": ["M"],
                "color_gr": [0.40],
                "color_ri": [0.05],
            }
        )
        result = add_composition_features(df)
        assert result.loc[0, "composition_class"] == "M"
        assert result.loc[0, "composition_source"] == "taxonomy"

    def test_sdss_nan_colors_stay_unknown(self) -> None:
        """NaN SDSS colors should not produce a classification."""
        df = pd.DataFrame(
            {
                "spkid": [1],
                "color_gr": [float("nan")],
                "color_ri": [float("nan")],
            }
        )
        result = add_composition_features(df)
        assert result.loc[0, "composition_class"] == "U"
