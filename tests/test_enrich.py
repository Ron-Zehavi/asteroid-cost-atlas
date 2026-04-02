from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.enrich import (
    DEFAULT_ALBEDO,
    _latest_clean_parquet,
    add_diameter_estimate,
    h_to_diameter_km,
    merge_lcdb,
)

# ---------------------------------------------------------------------------
# h_to_diameter_km
# ---------------------------------------------------------------------------


class TestHtoDiameter:
    def test_ceres_approximate(self) -> None:
        # Ceres: H≈3.53, albedo≈0.09, measured D≈939 km
        d = h_to_diameter_km(3.53, 0.09)
        assert 800 < d < 1100

    def test_default_albedo(self) -> None:
        d1 = h_to_diameter_km(15.0)
        d2 = h_to_diameter_km(15.0, DEFAULT_ALBEDO)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_brighter_means_larger(self) -> None:
        # Lower H = brighter = larger
        assert h_to_diameter_km(10.0) > h_to_diameter_km(20.0)

    def test_higher_albedo_means_smaller_estimate(self) -> None:
        # Same H but higher albedo → appears brighter → must be smaller
        assert h_to_diameter_km(15.0, 0.05) > h_to_diameter_km(15.0, 0.30)

    def test_known_value(self) -> None:
        # H=22, albedo=0.154 → D ≈ 0.134 km
        d = h_to_diameter_km(22.0, 0.154)
        assert 0.10 < d < 0.20

    def test_nan_h_returns_nan(self) -> None:
        assert math.isnan(h_to_diameter_km(float("nan")))

    def test_inf_h_returns_nan(self) -> None:
        assert math.isnan(h_to_diameter_km(float("inf")))

    def test_zero_albedo_returns_nan(self) -> None:
        assert math.isnan(h_to_diameter_km(15.0, 0.0))

    def test_negative_albedo_returns_nan(self) -> None:
        assert math.isnan(h_to_diameter_km(15.0, -0.1))

    def test_positive_result(self) -> None:
        assert h_to_diameter_km(20.0, 0.2) > 0


# ---------------------------------------------------------------------------
# add_diameter_estimate
# ---------------------------------------------------------------------------


class TestAddDiameterEstimate:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [1, 2, 3, 4, 5],
                "abs_magnitude": [3.53, 15.0, 22.0, float("nan"), 18.0],
                "diameter_km": [939.4, None, None, None, None],
                "albedo": [0.09, 0.20, None, None, 0.15],
            }
        )

    def test_adds_two_columns(self) -> None:
        result = add_diameter_estimate(self._sample_df())
        assert "diameter_estimated_km" in result.columns
        assert "diameter_source" in result.columns

    def test_measured_diameter_passed_through(self) -> None:
        result = add_diameter_estimate(self._sample_df())
        assert result.loc[0, "diameter_source"] == "measured"
        assert result.loc[0, "diameter_estimated_km"] == pytest.approx(939.4)

    def test_estimated_from_h_with_albedo(self) -> None:
        result = add_diameter_estimate(self._sample_df())
        assert result.loc[1, "diameter_source"] == "estimated"
        expected = h_to_diameter_km(15.0, 0.20)
        assert result.loc[1, "diameter_estimated_km"] == pytest.approx(expected, rel=1e-6)

    def test_estimated_from_h_default_albedo(self) -> None:
        result = add_diameter_estimate(self._sample_df())
        # Row 2: H=22, no albedo, no taxonomy → uses DEFAULT_ALBEDO
        assert result.loc[2, "diameter_source"] == "estimated"
        expected = h_to_diameter_km(22.0, DEFAULT_ALBEDO)
        assert result.loc[2, "diameter_estimated_km"] == pytest.approx(expected, rel=1e-6)

    def test_taxonomy_aware_prior_c_type(self) -> None:
        df = pd.DataFrame(
            {
                "abs_magnitude": [15.0],
                "diameter_km": [None],
                "albedo": [None],
                "taxonomy": ["C"],
            }
        )
        result = add_diameter_estimate(df)
        # C-type prior pV=0.06, not default 0.154
        expected = h_to_diameter_km(15.0, 0.06)
        assert result.loc[0, "diameter_estimated_km"] == pytest.approx(expected, rel=1e-6)

    def test_measured_albedo_overrides_taxonomy_prior(self) -> None:
        df = pd.DataFrame(
            {
                "abs_magnitude": [15.0],
                "diameter_km": [None],
                "albedo": [0.30],
                "taxonomy": ["C"],
            }
        )
        result = add_diameter_estimate(df)
        # Measured albedo 0.30 takes priority over C-type prior 0.06
        expected = h_to_diameter_km(15.0, 0.30)
        assert result.loc[0, "diameter_estimated_km"] == pytest.approx(expected, rel=1e-6)

    def test_unknown_taxonomy_falls_back_to_default(self) -> None:
        df = pd.DataFrame(
            {
                "abs_magnitude": [15.0],
                "diameter_km": [None],
                "albedo": [None],
                "taxonomy": ["ZZZ"],
            }
        )
        result = add_diameter_estimate(df)
        expected = h_to_diameter_km(15.0, DEFAULT_ALBEDO)
        assert result.loc[0, "diameter_estimated_km"] == pytest.approx(expected, rel=1e-6)

    def test_missing_h_produces_nan(self) -> None:
        result = add_diameter_estimate(self._sample_df())
        assert math.isnan(result.loc[3, "diameter_estimated_km"])
        assert pd.isna(result.loc[3, "diameter_source"])

    def test_does_not_mutate_input(self) -> None:
        df = self._sample_df()
        _ = add_diameter_estimate(df)
        assert "diameter_estimated_km" not in df.columns

    def test_preserves_row_count(self) -> None:
        df = self._sample_df()
        result = add_diameter_estimate(df)
        assert len(result) == len(df)

    def test_original_diameter_km_untouched(self) -> None:
        df = self._sample_df()
        result = add_diameter_estimate(df)
        assert result.loc[0, "diameter_km"] == pytest.approx(939.4)
        assert pd.isna(result.loc[1, "diameter_km"])

    def test_missing_abs_magnitude_column_raises(self) -> None:
        df = pd.DataFrame({"spkid": [1], "diameter_km": [10.0]})
        with pytest.raises(ValueError, match="abs_magnitude"):
            add_diameter_estimate(df)

    def test_no_diameter_column_still_works(self) -> None:
        df = pd.DataFrame({"abs_magnitude": [15.0, 20.0]})
        result = add_diameter_estimate(df)
        assert (result["diameter_source"] == "estimated").all()
        assert result["diameter_estimated_km"].notna().all()

    def test_all_measured_no_estimates(self) -> None:
        df = pd.DataFrame(
            {
                "abs_magnitude": [3.53, 5.0],
                "diameter_km": [939.4, 500.0],
                "albedo": [0.09, 0.15],
            }
        )
        result = add_diameter_estimate(df)
        assert (result["diameter_source"] == "measured").all()

    def test_existing_columns_overwritten(self) -> None:
        df = self._sample_df()
        df["diameter_estimated_km"] = 999.0
        df["diameter_source"] = "stale"
        result = add_diameter_estimate(df)
        assert result.loc[1, "diameter_source"] == "estimated"
        assert result.loc[1, "diameter_estimated_km"] != 999.0

    def test_estimated_values_positive(self) -> None:
        result = add_diameter_estimate(self._sample_df())
        estimated = result[result["diameter_source"] == "estimated"]
        assert (estimated["diameter_estimated_km"] > 0).all()


# ---------------------------------------------------------------------------
# merge_lcdb
# ---------------------------------------------------------------------------


class TestMergeLcdb:
    def _sbdb_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [20000001, 20000002, 20000003],
                "rotation_hours": [9.07, None, None],
                "albedo": [0.09, None, None],
            }
        )

    def _lcdb_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [20000001, 20000002, 20000004],
                "lcdb_rotation_hours": [9.1, 7.81, 5.34],
                "lcdb_albedo": [0.09, 0.16, 0.42],
                "taxonomy": ["C", "B", "V"],
            }
        )

    def _write_lcdb_parquet(self, path: Path) -> Path:
        parquet = path / "lcdb.parquet"
        self._lcdb_df().to_parquet(parquet, index=False)
        return parquet

    def test_fills_rotation_gap(self, tmp_path: Path) -> None:
        lcdb_path = self._write_lcdb_parquet(tmp_path)
        result = merge_lcdb(self._sbdb_df(), lcdb_path)
        # spkid 2000002: had no rotation, LCDB has 7.81
        row = result[result["spkid"] == 20000002].iloc[0]
        assert row["rotation_hours"] == pytest.approx(7.81)
        assert row["rotation_source"] == "lcdb"

    def test_preserves_sbdb_rotation(self, tmp_path: Path) -> None:
        lcdb_path = self._write_lcdb_parquet(tmp_path)
        result = merge_lcdb(self._sbdb_df(), lcdb_path)
        # spkid 2000001: already had 9.07 from SBDB
        row = result[result["spkid"] == 20000001].iloc[0]
        assert row["rotation_hours"] == pytest.approx(9.07)
        assert row["rotation_source"] == "sbdb"

    def test_fills_albedo_gap(self, tmp_path: Path) -> None:
        lcdb_path = self._write_lcdb_parquet(tmp_path)
        result = merge_lcdb(self._sbdb_df(), lcdb_path)
        row = result[result["spkid"] == 20000002].iloc[0]
        assert row["albedo"] == pytest.approx(0.16)

    def test_no_lcdb_match_stays_nan(self, tmp_path: Path) -> None:
        lcdb_path = self._write_lcdb_parquet(tmp_path)
        result = merge_lcdb(self._sbdb_df(), lcdb_path)
        row = result[result["spkid"] == 20000003].iloc[0]
        assert pd.isna(row["rotation_hours"])
        assert pd.isna(row["rotation_source"])

    def test_adds_taxonomy(self, tmp_path: Path) -> None:
        lcdb_path = self._write_lcdb_parquet(tmp_path)
        result = merge_lcdb(self._sbdb_df(), lcdb_path)
        row = result[result["spkid"] == 20000002].iloc[0]
        assert row["taxonomy"] == "B"

    def test_does_not_mutate_input(self, tmp_path: Path) -> None:
        df = self._sbdb_df()
        lcdb_path = self._write_lcdb_parquet(tmp_path)
        _ = merge_lcdb(df, lcdb_path)
        assert "rotation_source" not in df.columns

    def test_preserves_row_count(self, tmp_path: Path) -> None:
        lcdb_path = self._write_lcdb_parquet(tmp_path)
        result = merge_lcdb(self._sbdb_df(), lcdb_path)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# _latest_clean_parquet
# ---------------------------------------------------------------------------


class TestLatestCleanParquet:
    def _write_parquet(self, path: Path) -> None:
        pd.DataFrame({"a": [1]}).to_parquet(path, index=False)

    def test_returns_latest_by_name(self, tmp_path: Path) -> None:
        for name in [
            "sbdb_clean_20260101.parquet",
            "sbdb_clean_20260201.parquet",
            "sbdb_clean_20260330.parquet",
        ]:
            self._write_parquet(tmp_path / name)
        result = _latest_clean_parquet(tmp_path)
        assert result.name == "sbdb_clean_20260330.parquet"

    def test_raises_when_no_parquet(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="make clean-data"):
            _latest_clean_parquet(tmp_path)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [2000001, 2000002],
                "abs_magnitude": [3.53, 15.0],
                "diameter_km": [939.4, None],
                "albedo": [0.09, None],
                "rotation_hours": [9.07, None],
            }
        )

    def test_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from asteroid_cost_atlas.ingest import enrich

        sample = self._sample_df()
        fake_path = tmp_path / "fake.parquet"
        monkeypatch.setattr(enrich, "_latest_clean_parquet", lambda _: fake_path)
        monkeypatch.setattr(enrich, "_latest_lcdb_parquet", lambda _: None)
        monkeypatch.setattr(pd, "read_parquet", lambda _: sample)
        monkeypatch.setattr(
            pd.DataFrame, "to_parquet", lambda self, *a, **kw: None
        )

        assert enrich.main() == 0

    def test_scores_both_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from asteroid_cost_atlas.ingest import enrich

        sample = self._sample_df()
        saved: dict[str, Any] = {}

        def capture(self: pd.DataFrame, *a: Any, **kw: Any) -> None:
            saved["df"] = self.copy()

        fake_path = tmp_path / "fake.parquet"
        monkeypatch.setattr(enrich, "_latest_clean_parquet", lambda _: fake_path)
        monkeypatch.setattr(enrich, "_latest_lcdb_parquet", lambda _: None)
        monkeypatch.setattr(pd, "read_parquet", lambda _: sample)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", capture)

        enrich.main()
        assert saved["df"]["diameter_estimated_km"].notna().all()
