from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.utils.query import CostAtlasDB

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_parquet(tmp_path: Path) -> Path:
    """Write a small Parquet file that mirrors the real atlas schema."""
    df = pd.DataFrame(
        {
            "spkid":               [20000001, 20000002, 20000003, 20000004, 20000005],
            "name":                ["Ceres", "Pallas", "Juno", "Vesta", "Astraea"],
            "a_au":                [2.77,  2.77,  2.67,  2.36,  2.58],
            "eccentricity":        [0.079, 0.231, 0.256, 0.090, 0.190],
            "inclination_deg":     [10.6,  34.9,  13.0,  7.1,   5.4],
            "diameter_km":         [939.4, 513.0, 246.6, 522.8, 119.1],
            "rotation_hours":      [9.07,  7.81,  7.21,  5.34,  16.8],
            "albedo":              [0.09,  0.16,  0.21,  0.42,  0.27],
            "tisserand_jupiter":   [3.31,  3.04,  3.30,  3.53,  3.40],
            "delta_v_km_s":        [8.92,  15.27, 9.23,  7.64,  7.86],
            "inclination_penalty": [0.009, 0.090, 0.013, 0.004, 0.002],
        }
    )
    path = tmp_path / "sbdb_orbital_20260330.parquet"
    df.to_parquet(path, index=False)
    return path


@pytest.fixture()
def db(sample_parquet: Path) -> CostAtlasDB:
    return CostAtlasDB(sample_parquet)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            CostAtlasDB(tmp_path / "nonexistent.parquet")

    def test_from_processed_dir(self, tmp_path: Path, sample_parquet: Path) -> None:
        db = CostAtlasDB.from_processed_dir(tmp_path)
        assert db is not None

    def test_from_processed_dir_no_files_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            CostAtlasDB.from_processed_dir(tmp_path)

    def test_from_processed_dir_selects_latest(self, tmp_path: Path) -> None:
        for date in ["20260101", "20260201", "20260330"]:
            df = pd.DataFrame({"delta_v_km_s": [1.0], "tisserand_jupiter": [3.0],
                               "inclination_deg": [5.0]})
            df.to_parquet(tmp_path / f"sbdb_orbital_{date}.parquet", index=False)
        db = CostAtlasDB.from_processed_dir(tmp_path)
        assert "20260330" in str(db._parquet_path)


# ---------------------------------------------------------------------------
# sql()
# ---------------------------------------------------------------------------


class TestSql:
    def test_returns_dataframe(self, db: CostAtlasDB) -> None:
        result = db.sql("SELECT * FROM atlas")
        assert isinstance(result, pd.DataFrame)

    def test_row_count(self, db: CostAtlasDB) -> None:
        result = db.sql("SELECT * FROM atlas")
        assert len(result) == 5

    def test_column_names_accessible(self, db: CostAtlasDB) -> None:
        result = db.sql("SELECT name, delta_v_km_s FROM atlas")
        assert list(result.columns) == ["name", "delta_v_km_s"]


# ---------------------------------------------------------------------------
# top_accessible()
# ---------------------------------------------------------------------------


class TestTopAccessible:
    def test_returns_n_rows(self, db: CostAtlasDB) -> None:
        result = db.top_accessible(n=3)
        assert len(result) == 3

    def test_sorted_by_delta_v_ascending(self, db: CostAtlasDB) -> None:
        result = db.top_accessible(n=5)
        assert list(result["delta_v_km_s"]) == sorted(result["delta_v_km_s"])

    def test_max_delta_v_filter(self, db: CostAtlasDB) -> None:
        result = db.top_accessible(n=10, max_delta_v=9.0)
        assert (result["delta_v_km_s"] <= 9.0).all()

    def test_max_inclination_filter(self, db: CostAtlasDB) -> None:
        result = db.top_accessible(n=10, max_inclination=15.0)
        assert (result["inclination_deg"] <= 15.0).all()

    def test_combined_filters(self, db: CostAtlasDB) -> None:
        result = db.top_accessible(n=10, max_delta_v=10.0, max_inclination=15.0)
        assert (result["delta_v_km_s"] <= 10.0).all()
        assert (result["inclination_deg"] <= 15.0).all()

    def test_n_larger_than_dataset_returns_all(self, db: CostAtlasDB) -> None:
        result = db.top_accessible(n=1000)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# nea_candidates()
# ---------------------------------------------------------------------------


class TestNeaCandidates:
    def test_tisserand_range(self, db: CostAtlasDB) -> None:
        # Sample data has no T_J in [2, 3) — all are main belt (> 3)
        result = db.nea_candidates(n=10)
        assert len(result) == 0

    def test_nea_tisserand_range_enforced(self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "spkid": [1, 2, 3],
            "name": ["NEA-1", "NEA-2", "Main-Belt"],
            "a_au": [1.2, 1.5, 2.8],
            "eccentricity": [0.1, 0.2, 0.1],
            "inclination_deg": [5.0, 8.0, 10.0],
            "diameter_km": [0.5, 1.0, 10.0],
            "rotation_hours": [3.0, 5.0, 8.0],
            "albedo": [0.2, 0.1, 0.15],
            "tisserand_jupiter": [2.5, 2.8, 3.4],
            "delta_v_km_s": [5.5, 6.0, 9.0],
            "inclination_penalty": [0.002, 0.005, 0.008],
        })
        path = tmp_path / "sbdb_orbital_20260330.parquet"
        df.to_parquet(path, index=False)
        db = CostAtlasDB(path)
        result = db.nea_candidates(n=10)
        assert len(result) == 2
        assert (result["tisserand_jupiter"] >= 2).all()
        assert (result["tisserand_jupiter"] < 3).all()

    def test_max_delta_v_filter(self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "spkid": [1, 2],
            "name": ["A", "B"],
            "a_au": [1.2, 1.5],
            "eccentricity": [0.1, 0.2],
            "inclination_deg": [5.0, 8.0],
            "diameter_km": [0.5, 1.0],
            "rotation_hours": [3.0, 5.0],
            "albedo": [0.2, 0.1],
            "tisserand_jupiter": [2.5, 2.8],
            "delta_v_km_s": [5.5, 9.0],
            "inclination_penalty": [0.002, 0.005],
        })
        path = tmp_path / "sbdb_orbital_20260330.parquet"
        df.to_parquet(path, index=False)
        db = CostAtlasDB(path)
        result = db.nea_candidates(n=10, max_delta_v=6.0)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "A"


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------


class TestStats:
    def test_returns_single_row(self, db: CostAtlasDB) -> None:
        result = db.stats()
        assert len(result) == 1

    def test_expected_columns(self, db: CostAtlasDB) -> None:
        result = db.stats()
        assert set(result.columns) >= {
            "total_objects", "scored_objects", "nea_candidates",
            "min_delta_v", "max_delta_v", "median_delta_v", "avg_delta_v",
        }

    def test_total_objects(self, db: CostAtlasDB) -> None:
        assert db.stats()["total_objects"].iloc[0] == 5

    def test_min_max_delta_v(self, db: CostAtlasDB) -> None:
        stats = db.stats()
        assert stats["min_delta_v"].iloc[0] == pytest.approx(7.64, abs=0.01)
        assert stats["max_delta_v"].iloc[0] == pytest.approx(15.27, abs=0.01)


# ---------------------------------------------------------------------------
# delta_v_histogram()
# ---------------------------------------------------------------------------


class TestDeltaVHistogram:
    def test_returns_dataframe(self, db: CostAtlasDB) -> None:
        result = db.delta_v_histogram()
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns(self, db: CostAtlasDB) -> None:
        result = db.delta_v_histogram()
        assert list(result.columns) == ["bin_floor_km_s", "count"]

    def test_counts_sum_to_total(self, db: CostAtlasDB) -> None:
        result = db.delta_v_histogram()
        assert result["count"].sum() == 5

    def test_sorted_by_bin(self, db: CostAtlasDB) -> None:
        result = db.delta_v_histogram()
        assert list(result["bin_floor_km_s"]) == sorted(result["bin_floor_km_s"])

    def test_custom_bin_width(self, db: CostAtlasDB) -> None:
        result = db.delta_v_histogram(bin_width=5.0)
        assert all(b % 5.0 == pytest.approx(0.0, abs=1e-6) for b in result["bin_floor_km_s"])
