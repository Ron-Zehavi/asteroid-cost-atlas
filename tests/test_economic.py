from __future__ import annotations

import math

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.economic import (
    accessibility_score,
    add_economic_score,
    economic_score,
    estimated_mass_kg,
)


class TestEstimatedMassKg:
    def test_ceres_order_of_magnitude(self) -> None:
        # Ceres: D≈939km, C-type density 1300 → mass ~5.6e20
        mass = estimated_mass_kg(939.4, "C")
        assert 1e20 < mass < 1e21

    def test_larger_diameter_larger_mass(self) -> None:
        assert estimated_mass_kg(10.0, "S") > estimated_mass_kg(1.0, "S")

    def test_denser_class_heavier(self) -> None:
        # Same diameter, M-type denser than C-type
        assert estimated_mass_kg(1.0, "M") > estimated_mass_kg(1.0, "C")

    def test_zero_diameter_nan(self) -> None:
        assert math.isnan(estimated_mass_kg(0.0, "C"))

    def test_negative_diameter_nan(self) -> None:
        assert math.isnan(estimated_mass_kg(-1.0, "S"))

    def test_unknown_class_uses_default(self) -> None:
        mass = estimated_mass_kg(1.0, "U")
        assert mass > 0


class TestAccessibilityScore:
    def test_low_delta_v_high_accessibility(self) -> None:
        assert accessibility_score(1.0) > accessibility_score(10.0)

    def test_inverse_square(self) -> None:
        assert accessibility_score(2.0) == pytest.approx(0.25, rel=1e-9)

    def test_zero_returns_nan(self) -> None:
        assert math.isnan(accessibility_score(0.0))

    def test_negative_returns_nan(self) -> None:
        assert math.isnan(accessibility_score(-1.0))


class TestEconomicScore:
    def test_positive_inputs(self) -> None:
        score = economic_score(1e10, 500.0, 0.25)
        assert score > 0

    def test_nan_propagates(self) -> None:
        assert math.isnan(economic_score(float("nan"), 500.0, 0.25))


class TestAddEconomicScore:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [1, 2, 3, 4],
                "name": ["A", "B", "C", "D"],
                "diameter_estimated_km": [10.0, 1.0, 100.0, None],
                "delta_v_km_s": [5.0, 10.0, 3.0, 5.0],
                "composition_class": ["C", "S", "M", "C"],
                "resource_value_usd_per_kg": [500.0, 1.0, 50.0, 500.0],
            }
        )

    def test_adds_five_columns(self) -> None:
        result = add_economic_score(self._sample_df())
        for col in (
            "estimated_mass_kg", "estimated_value_usd",
            "accessibility", "economic_score", "economic_priority_rank",
        ):
            assert col in result.columns

    def test_rank_1_is_best(self) -> None:
        result = add_economic_score(self._sample_df())
        rank_1 = result[result["economic_priority_rank"] == 1]
        assert len(rank_1) == 1
        # Rank 1 should have the highest economic_score
        assert rank_1["economic_score"].iloc[0] == result["economic_score"].max()

    def test_missing_diameter_unscored(self) -> None:
        result = add_economic_score(self._sample_df())
        # Row 3 has no diameter → should be unranked
        assert math.isnan(result.loc[3, "economic_score"])
        assert math.isnan(result.loc[3, "economic_priority_rank"])

    def test_larger_c_type_ranks_higher_than_small_s(self) -> None:
        result = add_economic_score(self._sample_df())
        # 10km C-type at dv=5 should outrank 1km S-type at dv=10
        rank_a = result.loc[0, "economic_priority_rank"]
        rank_b = result.loc[1, "economic_priority_rank"]
        assert rank_a < rank_b  # lower rank = better

    def test_does_not_mutate_input(self) -> None:
        df = self._sample_df()
        _ = add_economic_score(df)
        assert "economic_score" not in df.columns

    def test_preserves_row_count(self) -> None:
        df = self._sample_df()
        assert len(add_economic_score(df)) == len(df)

    def test_mass_positive_for_valid(self) -> None:
        result = add_economic_score(self._sample_df())
        valid = result["estimated_mass_kg"].notna()
        assert (result.loc[valid, "estimated_mass_kg"] > 0).all()

    def test_value_positive_for_valid(self) -> None:
        result = add_economic_score(self._sample_df())
        valid = result["estimated_value_usd"].notna()
        assert (result.loc[valid, "estimated_value_usd"] > 0).all()

    def test_missing_required_column_raises(self) -> None:
        df = self._sample_df().drop(columns=["delta_v_km_s"])
        with pytest.raises(ValueError, match="missing required columns"):
            add_economic_score(df)

    def test_tied_scores_get_unique_ranks(self) -> None:
        df = pd.DataFrame(
            {
                "name": ["Alpha", "Beta"],
                "diameter_estimated_km": [10.0, 10.0],
                "delta_v_km_s": [5.0, 5.0],
                "composition_class": ["C", "C"],
                "resource_value_usd_per_kg": [500.0, 500.0],
            }
        )
        result = add_economic_score(df)
        ranks = result["economic_priority_rank"].dropna().tolist()
        assert sorted(ranks) == [1, 2]  # consecutive, no gaps

    def test_tied_scores_broken_by_name(self) -> None:
        df = pd.DataFrame(
            {
                "name": ["Bravo", "Alpha"],
                "diameter_estimated_km": [10.0, 10.0],
                "delta_v_km_s": [5.0, 5.0],
                "composition_class": ["C", "C"],
                "resource_value_usd_per_kg": [500.0, 500.0],
            }
        )
        result = add_economic_score(df)
        # Alpha sorts before Bravo → Alpha gets rank 1
        assert result.loc[1, "economic_priority_rank"] == 1  # Alpha
        assert result.loc[0, "economic_priority_rank"] == 2  # Bravo

    def test_all_ranks_unique_for_different_scores(self) -> None:
        result = add_economic_score(self._sample_df())
        ranked = result["economic_priority_rank"].dropna()
        assert ranked.is_unique
