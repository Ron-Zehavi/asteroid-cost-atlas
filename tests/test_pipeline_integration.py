"""
End-to-end pipeline integration test.

Runs clean() → add_orbital_features() → CostAtlasDB on a synthetic
10-row DataFrame to verify the stages compose correctly without any
stage-coupling bugs that unit tests could miss.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.clean_sbdb import clean
from asteroid_cost_atlas.scoring.orbital import add_orbital_features
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
        _ = add_orbital_features(cleaned)
        assert len(raw_df) == original_len
        assert set(raw_df.columns) == original_cols
