from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.orbital import (
    A_JUPITER_AU,
    _latest_clean_parquet,
    add_orbital_features,
    delta_v_proxy_km_s,
    inclination_penalty,
    tisserand_parameter,
)

# ---------------------------------------------------------------------------
# tisserand_parameter
# ---------------------------------------------------------------------------


class TestTisserandParameter:
    def test_main_belt_asteroid_above_3(self) -> None:
        # Ceres: a=2.77, e=0.079, i=10.6° → T_J should be > 3 (main belt)
        t = tisserand_parameter(2.77, 0.079, 10.6)
        assert t > 3.0

    def test_earth_like_orbit_high_value(self) -> None:
        # Earth-like orbit: a≈1, e≈0, i≈0 → T_J ≈ 6
        t = tisserand_parameter(1.0, 0.0, 0.0)
        expected = A_JUPITER_AU / 1.0 + 2.0 * math.sqrt(1.0 / A_JUPITER_AU)
        assert t == pytest.approx(expected, rel=1e-6)

    def test_coplanar_zero_eccentricity_formula(self) -> None:
        a = 3.0
        t = tisserand_parameter(a, 0.0, 0.0)
        assert t == pytest.approx(A_JUPITER_AU / a + 2.0 * math.sqrt(a / A_JUPITER_AU), rel=1e-6)

    def test_inclination_reduces_tisserand(self) -> None:
        t_low = tisserand_parameter(2.5, 0.1, 5.0)
        t_high = tisserand_parameter(2.5, 0.1, 40.0)
        assert t_low > t_high

    def test_invalid_a_returns_nan(self) -> None:
        assert math.isnan(tisserand_parameter(0.0, 0.1, 10.0))
        assert math.isnan(tisserand_parameter(-1.0, 0.1, 10.0))

    def test_parabolic_eccentricity_returns_nan(self) -> None:
        assert math.isnan(tisserand_parameter(1.0, 1.0, 0.0))

    def test_negative_eccentricity_returns_nan(self) -> None:
        assert math.isnan(tisserand_parameter(1.0, -0.1, 0.0))


# ---------------------------------------------------------------------------
# delta_v_proxy_km_s
# ---------------------------------------------------------------------------


class TestDeltaVProxy:
    def test_earth_orbit_zero_inclination_near_zero(self) -> None:
        # Transfer to a=1, i=0 → both burns are ~0
        dv = delta_v_proxy_km_s(1.0, 0.0, 0.0)
        assert dv == pytest.approx(0.0, abs=1e-9)

    def test_increases_with_inclination(self) -> None:
        dv_low = delta_v_proxy_km_s(1.5, 0.1, 5.0)
        dv_high = delta_v_proxy_km_s(1.5, 0.1, 45.0)
        assert dv_high > dv_low

    def test_increases_with_semi_major_axis(self) -> None:
        # Further orbit requires more delta-v (ignoring inclination)
        dv_near = delta_v_proxy_km_s(1.3, 0.0, 0.0)
        dv_far = delta_v_proxy_km_s(2.5, 0.0, 0.0)
        assert dv_far > dv_near

    def test_result_positive(self) -> None:
        assert delta_v_proxy_km_s(2.0, 0.2, 15.0) > 0.0

    def test_result_in_plausible_range_km_s(self) -> None:
        # Typical NEA delta-v should be between 3 and 15 km/s
        dv = delta_v_proxy_km_s(1.3, 0.15, 10.0)
        assert 1.0 < dv < 20.0

    def test_invalid_a_returns_nan(self) -> None:
        assert math.isnan(delta_v_proxy_km_s(0.0, 0.1, 10.0))
        assert math.isnan(delta_v_proxy_km_s(-2.0, 0.1, 10.0))

    def test_polar_orbit_inclination(self) -> None:
        # 90° inclination should produce a significant delta-v penalty
        dv_eq = delta_v_proxy_km_s(1.5, 0.0, 0.0)
        dv_pol = delta_v_proxy_km_s(1.5, 0.0, 90.0)
        assert dv_pol > dv_eq + 5.0  # at least 5 km/s extra


# ---------------------------------------------------------------------------
# inclination_penalty
# ---------------------------------------------------------------------------


class TestInclinationPenalty:
    def test_zero_inclination_is_zero(self) -> None:
        assert inclination_penalty(0.0) == pytest.approx(0.0, abs=1e-12)

    def test_ninety_degrees_is_half(self) -> None:
        assert inclination_penalty(90.0) == pytest.approx(0.5, rel=1e-6)

    def test_180_degrees_is_one(self) -> None:
        assert inclination_penalty(180.0) == pytest.approx(1.0, rel=1e-6)

    def test_monotonically_increasing(self) -> None:
        penalties = [inclination_penalty(i) for i in range(0, 181, 10)]
        assert all(a <= b for a, b in zip(penalties, penalties[1:]))

    def test_range_is_zero_to_one(self) -> None:
        for i in [0, 15, 30, 45, 60, 90, 120, 180]:
            p = inclination_penalty(i)
            assert 0.0 <= p <= 1.0


# ---------------------------------------------------------------------------
# add_orbital_features
# ---------------------------------------------------------------------------


class TestAddOrbitalFeatures:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [20000001, 20000002, 20000003],
                "name": ["Ceres", "Pallas", "Juno"],
                "a_au": [2.77, 2.77, 2.67],
                "eccentricity": [0.079, 0.231, 0.256],
                "inclination_deg": [10.6, 34.9, 13.0],
            }
        )

    def test_adds_three_columns(self) -> None:
        result = add_orbital_features(self._sample_df())
        assert "tisserand_jupiter" in result.columns
        assert "delta_v_km_s" in result.columns
        assert "inclination_penalty" in result.columns

    def test_does_not_mutate_input(self) -> None:
        df = self._sample_df()
        _ = add_orbital_features(df)
        assert "tisserand_jupiter" not in df.columns

    def test_preserves_row_count(self) -> None:
        df = self._sample_df()
        result = add_orbital_features(df)
        assert len(result) == len(df)

    def test_nan_rows_propagate_nan(self) -> None:
        df = self._sample_df()
        df.loc[1, "a_au"] = float("nan")
        result = add_orbital_features(df)
        assert math.isnan(result.loc[1, "tisserand_jupiter"])
        assert math.isnan(result.loc[1, "delta_v_km_s"])
        assert math.isnan(result.loc[1, "inclination_penalty"])

    def test_valid_rows_not_nan(self) -> None:
        result = add_orbital_features(self._sample_df())
        assert result["tisserand_jupiter"].notna().all()
        assert result["delta_v_km_s"].notna().all()
        assert result["inclination_penalty"].notna().all()

    def test_tisserand_main_belt_above_3(self) -> None:
        result = add_orbital_features(self._sample_df())
        assert (result["tisserand_jupiter"] > 3.0).all()

    def test_delta_v_positive(self) -> None:
        result = add_orbital_features(self._sample_df())
        assert (result["delta_v_km_s"] > 0).all()

    def test_inclination_penalty_in_range(self) -> None:
        result = add_orbital_features(self._sample_df())
        assert (result["inclination_penalty"] >= 0).all()
        assert (result["inclination_penalty"] <= 1).all()

    def test_invalid_a_zero_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "a_au"] = 0.0
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "delta_v_km_s"])
        assert math.isnan(result.loc[0, "tisserand_jupiter"])

    def test_invalid_a_negative_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "a_au"] = -1.0
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "delta_v_km_s"])

    def test_invalid_e_one_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "eccentricity"] = 1.0
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "tisserand_jupiter"])

    def test_invalid_e_greater_than_one_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "eccentricity"] = 1.5
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "tisserand_jupiter"])

    def test_invalid_e_negative_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "eccentricity"] = -0.1
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "tisserand_jupiter"])

    def test_inf_a_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "a_au"] = float("inf")
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "delta_v_km_s"])

    def test_inf_inclination_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "inclination_deg"] = float("inf")
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "inclination_penalty"])

    def test_invalid_row_does_not_affect_valid_rows(self) -> None:
        df = self._sample_df()
        df.loc[0, "a_au"] = 0.0
        result = add_orbital_features(df)
        assert result.loc[1, "delta_v_km_s"] > 0
        assert result.loc[2, "delta_v_km_s"] > 0

    def test_existing_columns_overwritten_not_stale(self) -> None:
        df = self._sample_df()
        df["tisserand_jupiter"] = 999.0
        df["delta_v_km_s"] = 999.0
        df["inclination_penalty"] = 999.0
        df.loc[0, "a_au"] = 0.0  # invalid — should become NaN, not keep 999.0
        result = add_orbital_features(df)
        assert math.isnan(result.loc[0, "tisserand_jupiter"])
        assert math.isnan(result.loc[0, "delta_v_km_s"])
        assert math.isnan(result.loc[0, "inclination_penalty"])

    def test_missing_required_column_raises(self) -> None:
        df = self._sample_df().drop(columns=["a_au"])
        with pytest.raises(ValueError, match="missing required columns"):
            add_orbital_features(df)

    def test_scalar_and_vectorised_agree(self) -> None:
        df = self._sample_df()
        result = add_orbital_features(df)
        for row in df.itertuples():
            assert result.loc[row.Index, "tisserand_jupiter"] == pytest.approx(
                tisserand_parameter(row.a_au, row.eccentricity, row.inclination_deg), rel=1e-6
            )
            assert result.loc[row.Index, "delta_v_km_s"] == pytest.approx(
                delta_v_proxy_km_s(row.a_au, row.eccentricity, row.inclination_deg), rel=1e-6
            )
            assert result.loc[row.Index, "inclination_penalty"] == pytest.approx(
                inclination_penalty(row.inclination_deg), rel=1e-6
            )


# ---------------------------------------------------------------------------
# _latest_clean_parquet
# ---------------------------------------------------------------------------


class TestLatestCleanParquet:
    def _write_parquet(self, path: Path) -> None:
        import pandas as pd
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

    def test_ignores_non_clean_parquets(self, tmp_path: Path) -> None:
        self._write_parquet(tmp_path / "sbdb_orbital_20260330.parquet")
        with pytest.raises(FileNotFoundError):
            _latest_clean_parquet(tmp_path)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "a_au": [2.77, 2.5],
                "eccentricity": [0.079, 0.1],
                "inclination_deg": [10.6, 5.0],
            }
        )

    def test_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.scoring import orbital

        sample = self._sample_df()
        monkeypatch.setattr(orbital, "_latest_clean_parquet", lambda _: tmp_path / "fake.parquet")
        monkeypatch.setattr(pd, "read_parquet", lambda _: sample)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, *a, **kw: None)

        assert orbital.main() == 0

    def test_scores_all_rows(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.scoring import orbital

        sample = self._sample_df()
        rows_saved: dict[str, Any] = {}

        def capture(self: pd.DataFrame, *a: Any, **kw: Any) -> None:
            rows_saved["df"] = self.copy()

        monkeypatch.setattr(orbital, "_latest_clean_parquet", lambda _: tmp_path / "fake.parquet")
        monkeypatch.setattr(pd, "read_parquet", lambda _: sample)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", capture)

        orbital.main()
        assert rows_saved["df"]["delta_v_km_s"].notna().all()

    def test_missing_parquet_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.scoring import orbital

        def raise_fnf(_: Path) -> Path:
            raise FileNotFoundError("no parquet")

        monkeypatch.setattr(orbital, "_latest_clean_parquet", raise_fnf)

        with pytest.raises(FileNotFoundError):
            orbital.main()
