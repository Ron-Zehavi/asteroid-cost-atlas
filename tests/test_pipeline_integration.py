"""
End-to-end pipeline integration test.

Runs the full chain: clean → orbital → physical → composition → economic → DuckDB
on a synthetic 10-row DataFrame to verify the stages compose correctly
without any stage-coupling bugs that unit tests could miss.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.clean_sbdb import clean
from asteroid_cost_atlas.ingest.enrich import add_diameter_estimate
from asteroid_cost_atlas.scoring.composition import add_composition_features
from asteroid_cost_atlas.scoring.economic import add_economic_score
from asteroid_cost_atlas.scoring.orbital import add_orbital_features
from asteroid_cost_atlas.scoring.physical import add_physical_features
from asteroid_cost_atlas.utils.query import CostAtlasDB


@pytest.fixture()
def raw_df() -> pd.DataFrame:
    """Synthetic raw catalog: 7 valid rows + 3 that should be cleaned."""
    return pd.DataFrame(
        {
            "spkid": list(range(20000001, 20000011)),
            "name": [f"Ast{i}" for i in range(10)],
            "a_au": [2.77, 1.5, 2.67, 2.36, 2.58, 1.3, 0.9,
                     0.0,         # a_au_le_zero → removed
                     float("nan"),  # non_finite → removed
                     2.5],          # valid
            "eccentricity": [0.079, 0.15, 0.256, 0.090, 0.190, 0.12, 0.08,
                              0.5, 0.1, 1.2],  # last: e_ge_one → removed
            "inclination_deg": [10.6, 5.0, 13.0, 7.1, 5.4, 12.0, 3.0,
                                 20.0, 15.0, 8.0],
            "diameter_km": [939.4, 0.5, 246.6, None, 119.1, 1.2, None,
                             50.0, 10.0, 0.3],
            "rotation_hours": [9.07, 1.0, 7.21, 5.34, None, 3.0, None,
                                8.0, 6.0, 24.0],
            "abs_magnitude": [3.5, 22.0, 5.2, 3.2, 7.0, 20.0, 18.0,
                               15.0, 10.0, 25.0],
            "albedo": [0.09, None, 0.21, 0.42, 0.27, None, None,
                        0.05, 0.15, None],
        }
    )


class TestPipelineIntegration:
    def test_clean_removes_three_rows(self, raw_df: pd.DataFrame) -> None:
        cleaned, removed = clean(raw_df)
        assert len(cleaned) == 7
        assert removed["a_au_le_zero"] == 1
        assert removed["non_finite_orbital_elements"] == 1
        assert removed["e_ge_one"] == 1

    def test_orbital_scoring_produces_no_nulls(self, raw_df: pd.DataFrame) -> None:
        cleaned, _ = clean(raw_df)
        scored = add_orbital_features(cleaned)
        assert scored["delta_v_km_s"].notna().all()
        assert scored["tisserand_jupiter"].notna().all()
        assert scored["inclination_penalty"].notna().all()

    def test_physical_scoring_after_orbital(self, raw_df: pd.DataFrame) -> None:
        cleaned, _ = clean(raw_df)
        orbital = add_orbital_features(cleaned)
        physical = add_physical_features(orbital)
        assert "surface_gravity_m_s2" in physical.columns
        assert "rotation_feasibility" in physical.columns
        assert "regolith_likelihood" in physical.columns

    def test_physical_scores_independent(self, raw_df: pd.DataFrame) -> None:
        cleaned, _ = clean(raw_df)
        orbital = add_orbital_features(cleaned)
        physical = add_physical_features(orbital)
        # Gravity scored wherever diameter is available
        has_diam = physical["diameter_km"].notna()
        assert physical.loc[has_diam, "surface_gravity_m_s2"].notna().all()
        assert physical.loc[~has_diam, "surface_gravity_m_s2"].isna().all()
        # Rotation scored wherever rotation_hours is available
        has_rot = physical["rotation_hours"].notna()
        assert physical.loc[has_rot, "rotation_feasibility"].notna().all()
        # Regolith only where both exist
        has_both = has_diam & has_rot
        assert physical.loc[has_both, "regolith_likelihood"].notna().all()

    def test_duckdb_query_sees_correct_row_count(
        self, raw_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        cleaned, _ = clean(raw_df)
        scored = add_orbital_features(cleaned)
        parquet_path = tmp_path / "atlas.parquet"
        scored.to_parquet(parquet_path, index=False)

        db = CostAtlasDB(parquet_path)
        stats = db.stats()
        assert stats["total_objects"].iloc[0] == 7

    def test_top_accessible_returns_sorted_results(
        self, raw_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        cleaned, _ = clean(raw_df)
        scored = add_orbital_features(cleaned)
        parquet_path = tmp_path / "atlas.parquet"
        scored.to_parquet(parquet_path, index=False)

        db = CostAtlasDB(parquet_path)
        top = db.top_accessible(n=3)
        assert len(top) <= 3
        dv = top["delta_v_km_s"].tolist()
        assert dv == sorted(dv)

    def test_cleaned_index_is_contiguous(self, raw_df: pd.DataFrame) -> None:
        cleaned, _ = clean(raw_df)
        assert list(cleaned.index) == list(range(len(cleaned)))

    def test_scored_columns_added(self, raw_df: pd.DataFrame) -> None:
        cleaned, _ = clean(raw_df)
        scored = add_orbital_features(cleaned)
        for col in ("tisserand_jupiter", "delta_v_km_s", "inclination_penalty"):
            assert col in scored.columns

    def test_input_not_mutated_through_pipeline(self, raw_df: pd.DataFrame) -> None:
        original_len = len(raw_df)
        original_cols = set(raw_df.columns)
        cleaned, _ = clean(raw_df)
        enriched = add_diameter_estimate(cleaned)
        orbital = add_orbital_features(enriched)
        physical = add_physical_features(orbital)
        composition = add_composition_features(physical)
        _ = add_economic_score(composition)
        assert len(raw_df) == original_len
        assert set(raw_df.columns) == original_cols

    def test_composition_after_physical(self, raw_df: pd.DataFrame) -> None:
        cleaned, _ = clean(raw_df)
        enriched = add_diameter_estimate(cleaned)
        orbital = add_orbital_features(enriched)
        physical = add_physical_features(orbital)
        composition = add_composition_features(physical)
        assert "composition_class" in composition.columns
        assert "resource_value_usd_per_kg" in composition.columns
        assert composition["composition_class"].notna().all()

    def test_economic_scoring_produces_ranking(self, raw_df: pd.DataFrame) -> None:
        cleaned, _ = clean(raw_df)
        enriched = add_diameter_estimate(cleaned)
        orbital = add_orbital_features(enriched)
        physical = add_physical_features(orbital)
        composition = add_composition_features(physical)
        atlas = add_economic_score(composition)
        assert "economic_priority_rank" in atlas.columns
        scored = atlas["economic_priority_rank"].notna()
        assert scored.sum() > 0
        # Ranks should be consecutive integers starting at 1
        ranks = atlas.loc[scored, "economic_priority_rank"].sort_values()
        assert ranks.iloc[0] == 1
        assert ranks.iloc[-1] == len(ranks)

    def test_full_pipeline_to_duckdb(
        self, raw_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        cleaned, _ = clean(raw_df)
        enriched = add_diameter_estimate(cleaned)
        orbital = add_orbital_features(enriched)
        physical = add_physical_features(orbital)
        composition = add_composition_features(physical)
        atlas = add_economic_score(composition)

        parquet_path = tmp_path / "atlas.parquet"
        atlas.to_parquet(parquet_path, index=False)

        with CostAtlasDB(parquet_path) as db:
            stats = db.stats()
            assert stats["total_objects"].iloc[0] == 7
            top = db.top_accessible(n=3)
            assert len(top) <= 3
            assert "economic_score" in top.columns
