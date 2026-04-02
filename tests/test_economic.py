from __future__ import annotations

import math

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.economic import (
    VE,
    accessibility_score,
    add_economic_score,
    economic_score,
    estimated_mass_kg,
    mission_cost_per_kg,
)


class TestEstimatedMassKg:
    def test_ceres_order_of_magnitude(self) -> None:
        mass = estimated_mass_kg(939.4, "C")
        assert 1e20 < mass < 1e21

    def test_larger_diameter_larger_mass(self) -> None:
        assert estimated_mass_kg(10.0, "S") > estimated_mass_kg(1.0, "S")

    def test_denser_class_heavier(self) -> None:
        assert estimated_mass_kg(1.0, "M") > estimated_mass_kg(1.0, "C")

    def test_zero_diameter_nan(self) -> None:
        assert math.isnan(estimated_mass_kg(0.0, "C"))

    def test_negative_diameter_nan(self) -> None:
        assert math.isnan(estimated_mass_kg(-1.0, "S"))

    def test_unknown_class_uses_default(self) -> None:
        assert estimated_mass_kg(1.0, "U") > 0


class TestMissionCostPerKg:
    def test_low_delta_v_near_leo_cost(self) -> None:
        # dv ≈ 0 should approach LEO cost
        cost = mission_cost_per_kg(0.01)
        assert 2700 < cost < 2800

    def test_increases_with_delta_v(self) -> None:
        assert mission_cost_per_kg(10.0) > mission_cost_per_kg(5.0)

    def test_exponential_growth(self) -> None:
        c5 = mission_cost_per_kg(5.0)
        c10 = mission_cost_per_kg(10.0)
        # Should grow much more than 2x
        assert c10 / c5 > 5

    def test_zero_returns_nan(self) -> None:
        assert math.isnan(mission_cost_per_kg(0.0))

    def test_known_value(self) -> None:
        # dv=5: cost = 2700 × exp(2×5/VE)
        expected = 2700 * math.exp(10.0 / VE)
        assert mission_cost_per_kg(5.0) == pytest.approx(expected, rel=1e-9)


class TestAccessibilityScore:
    def test_low_delta_v_high_accessibility(self) -> None:
        assert accessibility_score(1.0) > accessibility_score(10.0)

    def test_inverse_square(self) -> None:
        assert accessibility_score(2.0) == pytest.approx(0.25, rel=1e-9)

    def test_zero_returns_nan(self) -> None:
        assert math.isnan(accessibility_score(0.0))


class TestEconomicScore:
    def test_positive_inputs(self) -> None:
        assert economic_score(1e10, 50.0, 0.25) > 0

    def test_nan_propagates(self) -> None:
        assert math.isnan(economic_score(float("nan"), 50.0, 0.25))


class TestAddEconomicScore:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [1, 2, 3, 4],
                "name": ["A", "B", "C", "D"],
                "diameter_estimated_km": [10.0, 1.0, 100.0, None],
                "delta_v_km_s": [5.0, 10.0, 3.0, 5.0],
                "composition_class": ["C", "S", "M", "C"],
                "resource_value_usd_per_kg": [50.0, 8.0, 25.0, 50.0],
            }
        )

    def test_adds_seven_columns(self) -> None:
        result = add_economic_score(self._sample_df())
        for col in (
            "estimated_mass_kg", "estimated_value_usd",
            "mission_cost_usd_per_kg", "profit_ratio",
            "accessibility", "economic_score", "economic_priority_rank",
        ):
            assert col in result.columns

    def test_rank_1_is_best(self) -> None:
        result = add_economic_score(self._sample_df())
        rank_1 = result[result["economic_priority_rank"] == 1]
        assert len(rank_1) == 1
        assert rank_1["economic_score"].iloc[0] == result["economic_score"].max()

    def test_missing_diameter_unscored(self) -> None:
        result = add_economic_score(self._sample_df())
        assert math.isnan(result.loc[3, "economic_score"])
        assert math.isnan(result.loc[3, "economic_priority_rank"])

    def test_mission_cost_positive(self) -> None:
        result = add_economic_score(self._sample_df())
        valid = result["mission_cost_usd_per_kg"].notna()
        assert (result.loc[valid, "mission_cost_usd_per_kg"] > 0).all()

    def test_profit_ratio_computed(self) -> None:
        result = add_economic_score(self._sample_df())
        valid = result["profit_ratio"].notna()
        assert valid.sum() == 3  # 3 valid rows

    def test_tied_scores_get_unique_ranks(self) -> None:
        df = pd.DataFrame(
            {
                "name": ["Alpha", "Beta"],
                "diameter_estimated_km": [10.0, 10.0],
                "delta_v_km_s": [5.0, 5.0],
                "composition_class": ["C", "C"],
                "resource_value_usd_per_kg": [50.0, 50.0],
            }
        )
        result = add_economic_score(df)
        ranks = result["economic_priority_rank"].dropna().tolist()
        assert sorted(ranks) == [1, 2]

    def test_tied_scores_broken_by_name(self) -> None:
        df = pd.DataFrame(
            {
                "name": ["Bravo", "Alpha"],
                "diameter_estimated_km": [10.0, 10.0],
                "delta_v_km_s": [5.0, 5.0],
                "composition_class": ["C", "C"],
                "resource_value_usd_per_kg": [50.0, 50.0],
            }
        )
        result = add_economic_score(df)
        assert result.loc[1, "economic_priority_rank"] == 1  # Alpha
        assert result.loc[0, "economic_priority_rank"] == 2  # Bravo

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

    def test_missing_required_column_raises(self) -> None:
        df = self._sample_df().drop(columns=["delta_v_km_s"])
        with pytest.raises(ValueError, match="missing required columns"):
            add_economic_score(df)

    def test_all_ranks_unique_for_different_scores(self) -> None:
        result = add_economic_score(self._sample_df())
        ranked = result["economic_priority_rank"].dropna()
        assert ranked.is_unique
