from __future__ import annotations

import math

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.economic import (
    FALCON_LEO_COST,
    MISSION_MIN_COST,
    VE,
    accessibility_score,
    add_economic_score,
    estimated_mass_kg,
    mission_cost_per_kg,
)


class TestEstimatedMassKg:
    def test_ceres_order_of_magnitude(self) -> None:
        assert 1e20 < estimated_mass_kg(939.4, "C") < 1e21

    def test_larger_diameter_larger_mass(self) -> None:
        assert estimated_mass_kg(10.0, "S") > estimated_mass_kg(1.0, "S")

    def test_denser_class_heavier(self) -> None:
        assert estimated_mass_kg(1.0, "M") > estimated_mass_kg(1.0, "C")

    def test_zero_diameter_nan(self) -> None:
        assert math.isnan(estimated_mass_kg(0.0, "C"))


class TestMissionCostPerKg:
    def test_low_dv_near_leo_cost(self) -> None:
        assert 2700 < mission_cost_per_kg(0.01) < 2800

    def test_increases_with_dv(self) -> None:
        assert mission_cost_per_kg(10.0) > mission_cost_per_kg(5.0)

    def test_known_value(self) -> None:
        expected = FALCON_LEO_COST * math.exp(10.0 / VE)
        assert mission_cost_per_kg(5.0) == pytest.approx(expected, rel=1e-9)

    def test_zero_returns_nan(self) -> None:
        assert math.isnan(mission_cost_per_kg(0.0))


class TestAccessibilityScore:
    def test_inverse_square(self) -> None:
        assert accessibility_score(2.0) == pytest.approx(0.25, rel=1e-9)

    def test_zero_returns_nan(self) -> None:
        assert math.isnan(accessibility_score(0.0))


class TestAddEconomicScore:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [1, 2, 3, 4],
                "name": ["SmallClose", "SmallFar", "HugeClose", "NoData"],
                "diameter_estimated_km": [1.0, 1.0, 500.0, None],
                "delta_v_km_s": [2.0, 10.0, 2.0, 5.0],
                "composition_class": ["M", "M", "M", "M"],
                "resource_value_usd_per_kg": [25.0, 25.0, 25.0, 25.0],
                "specimen_value_per_kg": [35000.0, 35000.0, 35000.0, 35000.0],
                "platinum_ppm": [15.0, 15.0, 15.0, 15.0],
                "palladium_ppm": [8.0, 8.0, 8.0, 8.0],
                "rhodium_ppm": [2.0, 2.0, 2.0, 2.0],
                "iridium_ppm": [5.0, 5.0, 5.0, 5.0],
                "osmium_ppm": [5.0, 5.0, 5.0, 5.0],
                "ruthenium_ppm": [6.0, 6.0, 6.0, 6.0],
                "gold_ppm": [1.0, 1.0, 1.0, 1.0],
            }
        )

    def test_adds_core_columns(self) -> None:
        result = add_economic_score(self._sample_df())
        for col in (
            "estimated_mass_kg", "mission_cost_usd_per_kg",
            "margin_per_kg", "break_even_kg", "min_viable_kg",
            "is_viable", "missions_supported",
            "campaign_revenue_usd", "campaign_cost_usd", "campaign_profit_usd",
            "economic_score", "economic_priority_rank",
        ):
            assert col in result.columns

    def test_adds_per_metal_columns(self) -> None:
        result = add_economic_score(self._sample_df())
        for metal in ["platinum", "palladium", "rhodium", "gold"]:
            assert f"extractable_{metal}_kg" in result.columns

    def test_margin_positive_at_low_dv(self) -> None:
        result = add_economic_score(self._sample_df())
        # dv=2: transport ≈ $9,630 → margin ≈ $35K - $9.6K - $5K ≈ $20K
        assert result.loc[0, "margin_per_kg"] > 0

    def test_margin_negative_at_high_dv(self) -> None:
        result = add_economic_score(self._sample_df())
        # dv=10: transport ≈ $1.5M >> specimen value
        assert result.loc[1, "margin_per_kg"] < 0

    def test_break_even_nan_when_margin_negative(self) -> None:
        result = add_economic_score(self._sample_df())
        assert math.isnan(result.loc[1, "break_even_kg"])

    def test_break_even_finite_when_margin_positive(self) -> None:
        result = add_economic_score(self._sample_df())
        be = result.loc[0, "break_even_kg"]
        assert math.isfinite(be) and be > 0

    def test_break_even_equals_total_fixed_over_margin(self) -> None:
        result = add_economic_score(self._sample_df())
        margin = result.loc[0, "margin_per_kg"]
        transport = result.loc[0, "mission_cost_usd_per_kg"]
        total_fixed = MISSION_MIN_COST + 1000.0 * transport
        be = result.loc[0, "break_even_kg"]
        assert be == pytest.approx(total_fixed / margin, rel=1e-6)

    def test_tiny_asteroid_not_viable(self) -> None:
        # 0.001 km (1 meter) M-type: mass ~2.8 kg, extractable ~0.00004 kg
        df = self._sample_df()
        df.loc[0, "diameter_estimated_km"] = 0.001
        result = add_economic_score(df)
        assert not bool(result.loc[0, "is_viable"])

    def test_1km_m_type_viable_at_low_dv(self) -> None:
        result = add_economic_score(self._sample_df())
        # 1km M-type at dv=2: ~35M kg extractable >> break-even ~15K kg
        assert bool(result.loc[0, "is_viable"]) is True

    def test_huge_asteroid_viable(self) -> None:
        result = add_economic_score(self._sample_df())
        assert bool(result.loc[2, "is_viable"]) is True

    def test_high_dv_not_viable(self) -> None:
        result = add_economic_score(self._sample_df())
        # dv=10: margin < 0 → impossible to break even
        assert not bool(result.loc[1, "is_viable"])

    def test_viable_has_campaign_data(self) -> None:
        result = add_economic_score(self._sample_df())
        viable = result[result["is_viable"]]
        assert len(viable) > 0
        assert viable["campaign_revenue_usd"].notna().all()
        assert viable["missions_supported"].gt(0).all()

    def test_missions_supported_for_huge_asteroid(self) -> None:
        result = add_economic_score(self._sample_df())
        assert result.loc[2, "missions_supported"] > 0

    def test_missing_data_unscored(self) -> None:
        result = add_economic_score(self._sample_df())
        assert math.isnan(result.loc[3, "economic_score"])

    def test_rank_1_is_best(self) -> None:
        result = add_economic_score(self._sample_df())
        rank_1 = result[result["economic_priority_rank"] == 1]
        assert len(rank_1) == 1

    def test_does_not_mutate_input(self) -> None:
        df = self._sample_df()
        _ = add_economic_score(df)
        assert "economic_score" not in df.columns

    def test_preserves_row_count(self) -> None:
        df = self._sample_df()
        assert len(add_economic_score(df)) == len(df)

    def test_missing_required_column_raises(self) -> None:
        df = self._sample_df().drop(columns=["delta_v_km_s"])
        with pytest.raises(ValueError, match="missing required columns"):
            add_economic_score(df)
