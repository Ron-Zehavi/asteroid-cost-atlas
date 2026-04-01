from __future__ import annotations

import pandas as pd

from asteroid_cost_atlas.scoring.composition import (
    _VALUE_PER_KG,
    add_composition_features,
    classify_albedo,
    classify_taxonomy,
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
    def test_known_classes(self) -> None:
        assert resource_value_per_kg("C") == 500.0
        assert resource_value_per_kg("M") == 50.0
        assert resource_value_per_kg("S") == 1.0

    def test_unknown_gets_default(self) -> None:
        assert resource_value_per_kg("U") == _VALUE_PER_KG["U"]
        assert resource_value_per_kg("???") == _VALUE_PER_KG["U"]


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

    def test_adds_three_columns(self) -> None:
        result = add_composition_features(self._sample_df())
        assert "composition_class" in result.columns
        assert "composition_source" in result.columns
        assert "resource_value_usd_per_kg" in result.columns

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
        # Row 3: no taxonomy/spectral, albedo=0.04 → C
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
