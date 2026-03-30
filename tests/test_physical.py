from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from asteroid_cost_atlas.scoring.physical import (
    _latest_orbital_parquet,
    add_physical_features,
    regolith_likelihood,
    rotation_feasibility,
    surface_gravity_m_s2,
)

# ---------------------------------------------------------------------------
# surface_gravity_m_s2
# ---------------------------------------------------------------------------


class TestSurfaceGravity:
    def test_ceres_approximate(self) -> None:
        # Ceres: D ≈ 939 km, actual g ≈ 0.28 m/s²
        g = surface_gravity_m_s2(939.4)
        assert 0.20 < g < 0.35

    def test_small_asteroid(self) -> None:
        g = surface_gravity_m_s2(0.5)
        assert g > 0

    def test_larger_diameter_gives_higher_gravity(self) -> None:
        assert surface_gravity_m_s2(100.0) > surface_gravity_m_s2(10.0)

    def test_linearly_proportional_to_diameter(self) -> None:
        g1 = surface_gravity_m_s2(10.0)
        g2 = surface_gravity_m_s2(20.0)
        assert g2 == pytest.approx(2.0 * g1, rel=1e-9)

    def test_zero_diameter_returns_nan(self) -> None:
        assert math.isnan(surface_gravity_m_s2(0.0))

    def test_negative_diameter_returns_nan(self) -> None:
        assert math.isnan(surface_gravity_m_s2(-10.0))

    def test_inf_diameter_returns_nan(self) -> None:
        assert math.isnan(surface_gravity_m_s2(float("inf")))

    def test_nan_diameter_returns_nan(self) -> None:
        assert math.isnan(surface_gravity_m_s2(float("nan")))


# ---------------------------------------------------------------------------
# rotation_feasibility
# ---------------------------------------------------------------------------


class TestRotationFeasibility:
    def test_very_fast_is_zero(self) -> None:
        assert rotation_feasibility(1.0) == 0.0

    def test_spin_barrier_is_zero(self) -> None:
        assert rotation_feasibility(1.5) == 0.0

    def test_ramp_up_midpoint(self) -> None:
        assert rotation_feasibility(3.0) == pytest.approx(0.5, rel=1e-6)

    def test_at_4h_is_one(self) -> None:
        assert rotation_feasibility(4.0) == pytest.approx(1.0, rel=1e-6)

    def test_ideal_range(self) -> None:
        for h in [5, 10, 24, 50, 100]:
            assert rotation_feasibility(float(h)) == pytest.approx(1.0, rel=1e-6)

    def test_slow_ramp_down_midpoint(self) -> None:
        # At 300h: 1.0 - 0.5 * (300-100)/400 = 1.0 - 0.25 = 0.75
        assert rotation_feasibility(300.0) == pytest.approx(0.75, rel=1e-6)

    def test_at_500h_is_half(self) -> None:
        assert rotation_feasibility(500.0) == pytest.approx(0.5, rel=1e-6)

    def test_very_slow_is_half(self) -> None:
        assert rotation_feasibility(1000.0) == pytest.approx(0.5, rel=1e-6)

    def test_zero_period_returns_nan(self) -> None:
        assert math.isnan(rotation_feasibility(0.0))

    def test_negative_period_returns_nan(self) -> None:
        assert math.isnan(rotation_feasibility(-5.0))

    def test_inf_period_returns_nan(self) -> None:
        assert math.isnan(rotation_feasibility(float("inf")))

    def test_monotonic_in_ideal_ramp(self) -> None:
        scores = [rotation_feasibility(h) for h in [2.0, 2.5, 3.0, 3.5, 4.0]]
        assert all(a <= b for a, b in zip(scores, scores[1:]))


# ---------------------------------------------------------------------------
# regolith_likelihood
# ---------------------------------------------------------------------------


class TestRegolithLikelihood:
    def test_large_slow_rotator_near_one(self) -> None:
        r = regolith_likelihood(100.0, 10.0)
        assert r == pytest.approx(1.0, rel=1e-6)

    def test_tiny_asteroid_near_zero(self) -> None:
        r = regolith_likelihood(0.05, 10.0)
        assert r == pytest.approx(0.0, abs=1e-9)

    def test_fast_rotator_near_zero(self) -> None:
        r = regolith_likelihood(10.0, 1.5)
        assert r == pytest.approx(0.0, abs=1e-9)

    def test_borderline_size(self) -> None:
        # D=0.15 → size_factor=0, D=1.0 → size_factor=1
        assert regolith_likelihood(0.15, 10.0) == pytest.approx(0.0, abs=1e-9)
        assert regolith_likelihood(1.0, 10.0) == pytest.approx(1.0, rel=1e-6)

    def test_borderline_rotation(self) -> None:
        # p=2h → rot_factor=0, p=4h → rot_factor=1
        assert regolith_likelihood(10.0, 2.0) == pytest.approx(0.0, abs=1e-9)
        assert regolith_likelihood(10.0, 4.0) == pytest.approx(1.0, rel=1e-6)

    def test_zero_diameter_returns_nan(self) -> None:
        assert math.isnan(regolith_likelihood(0.0, 10.0))

    def test_zero_period_returns_nan(self) -> None:
        assert math.isnan(regolith_likelihood(10.0, 0.0))

    def test_negative_inputs_return_nan(self) -> None:
        assert math.isnan(regolith_likelihood(-1.0, 10.0))
        assert math.isnan(regolith_likelihood(10.0, -1.0))

    def test_inf_inputs_return_nan(self) -> None:
        assert math.isnan(regolith_likelihood(float("inf"), 10.0))
        assert math.isnan(regolith_likelihood(10.0, float("inf")))

    def test_increases_with_diameter(self) -> None:
        r1 = regolith_likelihood(0.3, 10.0)
        r2 = regolith_likelihood(0.8, 10.0)
        assert r2 > r1

    def test_increases_with_period(self) -> None:
        r1 = regolith_likelihood(10.0, 2.5)
        r2 = regolith_likelihood(10.0, 3.5)
        assert r2 > r1


# ---------------------------------------------------------------------------
# add_physical_features
# ---------------------------------------------------------------------------


class TestAddPhysicalFeatures:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "spkid": [20000001, 20000002, 20000003],
                "name": ["Ceres", "Pallas", "Juno"],
                "diameter_km": [939.4, 513.0, 246.6],
                "rotation_hours": [9.07, 7.81, 7.21],
            }
        )

    def test_adds_three_columns(self) -> None:
        result = add_physical_features(self._sample_df())
        assert "surface_gravity_m_s2" in result.columns
        assert "rotation_feasibility" in result.columns
        assert "regolith_likelihood" in result.columns

    def test_does_not_mutate_input(self) -> None:
        df = self._sample_df()
        _ = add_physical_features(df)
        assert "surface_gravity_m_s2" not in df.columns

    def test_preserves_row_count(self) -> None:
        df = self._sample_df()
        result = add_physical_features(df)
        assert len(result) == len(df)

    def test_valid_rows_not_nan(self) -> None:
        result = add_physical_features(self._sample_df())
        assert result["surface_gravity_m_s2"].notna().all()
        assert result["rotation_feasibility"].notna().all()
        assert result["regolith_likelihood"].notna().all()

    def test_nan_diameter_only_affects_gravity_and_regolith(self) -> None:
        df = self._sample_df()
        df.loc[1, "diameter_km"] = float("nan")
        result = add_physical_features(df)
        assert math.isnan(result.loc[1, "surface_gravity_m_s2"])
        # Rotation feasibility is independent of diameter
        assert not math.isnan(result.loc[1, "rotation_feasibility"])
        assert math.isnan(result.loc[1, "regolith_likelihood"])

    def test_nan_rotation_only_affects_rotation_and_regolith(self) -> None:
        df = self._sample_df()
        df.loc[1, "rotation_hours"] = float("nan")
        result = add_physical_features(df)
        # Gravity is independent of rotation
        assert not math.isnan(result.loc[1, "surface_gravity_m_s2"])
        assert math.isnan(result.loc[1, "rotation_feasibility"])
        assert math.isnan(result.loc[1, "regolith_likelihood"])

    def test_zero_diameter_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "diameter_km"] = 0.0
        result = add_physical_features(df)
        assert math.isnan(result.loc[0, "surface_gravity_m_s2"])

    def test_negative_rotation_produces_nan(self) -> None:
        df = self._sample_df()
        df.loc[0, "rotation_hours"] = -5.0
        result = add_physical_features(df)
        assert math.isnan(result.loc[0, "rotation_feasibility"])

    def test_invalid_row_does_not_affect_valid(self) -> None:
        df = self._sample_df()
        df.loc[0, "diameter_km"] = float("nan")
        result = add_physical_features(df)
        assert result.loc[1, "surface_gravity_m_s2"] > 0
        assert result.loc[2, "surface_gravity_m_s2"] > 0

    def test_gravity_positive_for_valid(self) -> None:
        result = add_physical_features(self._sample_df())
        assert (result["surface_gravity_m_s2"] > 0).all()

    def test_rotation_feasibility_in_range(self) -> None:
        result = add_physical_features(self._sample_df())
        assert (result["rotation_feasibility"] >= 0).all()
        assert (result["rotation_feasibility"] <= 1).all()

    def test_regolith_likelihood_in_range(self) -> None:
        result = add_physical_features(self._sample_df())
        assert (result["regolith_likelihood"] >= 0).all()
        assert (result["regolith_likelihood"] <= 1).all()

    def test_fast_rotator_zero_feasibility(self) -> None:
        df = self._sample_df()
        df.loc[0, "rotation_hours"] = 1.0
        result = add_physical_features(df)
        assert result.loc[0, "rotation_feasibility"] == pytest.approx(0.0)

    def test_existing_columns_overwritten(self) -> None:
        df = self._sample_df()
        df["surface_gravity_m_s2"] = 999.0
        df.loc[0, "diameter_km"] = float("nan")
        result = add_physical_features(df)
        assert math.isnan(result.loc[0, "surface_gravity_m_s2"])

    def test_diameter_only_still_works(self) -> None:
        df = self._sample_df().drop(columns=["rotation_hours"])
        result = add_physical_features(df)
        assert result["surface_gravity_m_s2"].notna().all()
        assert result["rotation_feasibility"].isna().all()

    def test_rotation_only_still_works(self) -> None:
        df = self._sample_df().drop(columns=["diameter_km"])
        result = add_physical_features(df)
        assert result["rotation_feasibility"].notna().all()
        assert result["surface_gravity_m_s2"].isna().all()

    def test_no_columns_raises(self) -> None:
        df = self._sample_df().drop(columns=["diameter_km", "rotation_hours"])
        with pytest.raises(ValueError, match="must have at least one"):
            add_physical_features(df)

    def test_prefers_estimated_diameter(self) -> None:
        df = self._sample_df()
        df["diameter_estimated_km"] = [1000.0, 600.0, 300.0]
        result = add_physical_features(df)
        # Should use diameter_estimated_km, not diameter_km
        expected_g = surface_gravity_m_s2(1000.0)
        assert result.loc[0, "surface_gravity_m_s2"] == pytest.approx(expected_g, rel=1e-6)

    def test_scalar_and_vectorised_agree(self) -> None:
        df = self._sample_df()
        result = add_physical_features(df)
        for row in df.itertuples():
            assert result.loc[row.Index, "surface_gravity_m_s2"] == pytest.approx(
                surface_gravity_m_s2(row.diameter_km), rel=1e-6
            )
            assert result.loc[row.Index, "rotation_feasibility"] == pytest.approx(
                rotation_feasibility(row.rotation_hours), rel=1e-6
            )
            assert result.loc[row.Index, "regolith_likelihood"] == pytest.approx(
                regolith_likelihood(row.diameter_km, row.rotation_hours), rel=1e-6
            )


# ---------------------------------------------------------------------------
# _latest_orbital_parquet
# ---------------------------------------------------------------------------


class TestLatestOrbitalParquet:
    def _write_parquet(self, path: Path) -> None:
        pd.DataFrame({"a": [1]}).to_parquet(path, index=False)

    def test_returns_latest_by_name(self, tmp_path: Path) -> None:
        for name in [
            "sbdb_orbital_20260101.parquet",
            "sbdb_orbital_20260201.parquet",
            "sbdb_orbital_20260330.parquet",
        ]:
            self._write_parquet(tmp_path / name)
        result = _latest_orbital_parquet(tmp_path)
        assert result.name == "sbdb_orbital_20260330.parquet"

    def test_raises_when_no_parquet(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="make score-orbital"):
            _latest_orbital_parquet(tmp_path)

    def test_ignores_non_orbital_parquets(self, tmp_path: Path) -> None:
        self._write_parquet(tmp_path / "sbdb_clean_20260330.parquet")
        with pytest.raises(FileNotFoundError):
            _latest_orbital_parquet(tmp_path)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "diameter_km": [939.4, 513.0],
                "rotation_hours": [9.07, 7.81],
            }
        )

    def test_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.scoring import physical

        sample = self._sample_df()
        fake_path = tmp_path / "fake.parquet"
        monkeypatch.setattr(physical, "_latest_orbital_parquet", lambda _: fake_path)
        monkeypatch.setattr(pd, "read_parquet", lambda _: sample)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, *a, **kw: None)

        assert physical.main() == 0

    def test_scores_valid_rows(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.scoring import physical

        sample = self._sample_df()
        saved: dict[str, Any] = {}

        def capture(self: pd.DataFrame, *a: Any, **kw: Any) -> None:
            saved["df"] = self.copy()

        fake_path = tmp_path / "fake.parquet"
        monkeypatch.setattr(physical, "_latest_orbital_parquet", lambda _: fake_path)
        monkeypatch.setattr(pd, "read_parquet", lambda _: sample)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", capture)

        physical.main()
        assert saved["df"]["surface_gravity_m_s2"].notna().all()

    def test_missing_parquet_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.scoring import physical

        def raise_fnf(_: Path) -> Path:
            raise FileNotFoundError("no parquet")

        monkeypatch.setattr(physical, "_latest_orbital_parquet", raise_fnf)

        with pytest.raises(FileNotFoundError):
            physical.main()
