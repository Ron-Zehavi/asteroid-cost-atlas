from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.clean_sbdb import (
    _latest_raw_csv,
    _write_metadata,
    clean,
)


def _make_df(**overrides: list) -> pd.DataFrame:
    """Build a minimal valid DataFrame with optional column overrides."""
    base = {
        "spkid":           [20000001, 20000002, 20000003, 20000004, 20000005],
        "name":            ["Ceres", "Pallas", "Juno", "Vesta", "Astraea"],
        "a_au":            [2.77, 2.77, 2.67, 2.36, 2.58],
        "eccentricity":    [0.079, 0.231, 0.256, 0.090, 0.190],
        "inclination_deg": [10.6, 34.9, 13.0, 7.1, 5.4],
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# Clean data passes through unchanged
# ---------------------------------------------------------------------------


class TestCleanPassthrough:
    def test_all_valid_rows_kept(self) -> None:
        df = _make_df()
        result, removed = clean(df)
        assert len(result) == 5

    def test_no_rows_reported_removed(self) -> None:
        df = _make_df()
        _, removed = clean(df)
        assert sum(removed.values()) == 0

    def test_columns_unchanged(self) -> None:
        df = _make_df()
        result, _ = clean(df)
        assert list(result.columns) == list(df.columns)

    def test_does_not_mutate_input(self) -> None:
        df = _make_df()
        original_len = len(df)
        clean(df)
        assert len(df) == original_len


# ---------------------------------------------------------------------------
# Rule: non-finite orbital elements
# ---------------------------------------------------------------------------


class TestNonFiniteRule:
    def test_inf_a_removed(self) -> None:
        df = _make_df(a_au=[float("inf"), 2.77, 2.67, 2.36, 2.58])
        result, removed = clean(df)
        assert len(result) == 4
        assert removed["non_finite_orbital_elements"] == 1

    def test_nan_eccentricity_removed(self) -> None:
        df = _make_df(eccentricity=[float("nan"), 0.231, 0.256, 0.090, 0.190])
        result, removed = clean(df)
        assert len(result) == 4
        assert removed["non_finite_orbital_elements"] == 1

    def test_nan_inclination_removed(self) -> None:
        df = _make_df(inclination_deg=[float("nan"), 34.9, 13.0, 7.1, 5.4])
        result, removed = clean(df)
        assert len(result) == 4
        assert removed["non_finite_orbital_elements"] == 1


# ---------------------------------------------------------------------------
# Rule: a_au <= 0
# ---------------------------------------------------------------------------


class TestAuRule:
    def test_zero_a_removed(self) -> None:
        df = _make_df(a_au=[0.0, 2.77, 2.67, 2.36, 2.58])
        result, removed = clean(df)
        assert len(result) == 4
        assert removed["a_au_le_zero"] == 1

    def test_negative_a_removed(self) -> None:
        df = _make_df(a_au=[-433e9, 2.77, 2.67, 2.36, 2.58])
        result, removed = clean(df)
        assert len(result) == 4
        assert removed["a_au_le_zero"] == 1

    def test_multiple_bad_a_removed(self) -> None:
        df = _make_df(a_au=[-1.0, -2.0, 2.67, 2.36, 2.58])
        result, removed = clean(df)
        assert len(result) == 3
        assert removed["a_au_le_zero"] == 2


# ---------------------------------------------------------------------------
# Rule: e >= 1 (hyperbolic)
# ---------------------------------------------------------------------------


class TestEccentricityRule:
    def test_e_equal_one_removed(self) -> None:
        df = _make_df(eccentricity=[1.0, 0.231, 0.256, 0.090, 0.190])
        result, removed = clean(df)
        assert len(result) == 4
        assert removed["e_ge_one"] == 1

    def test_e_greater_than_one_removed(self) -> None:
        df = _make_df(eccentricity=[6.14, 0.231, 0.256, 0.090, 0.190])
        result, removed = clean(df)
        assert len(result) == 4
        assert removed["e_ge_one"] == 1

    def test_e_just_below_one_kept(self) -> None:
        df = _make_df(eccentricity=[0.9999, 0.231, 0.256, 0.090, 0.190])
        result, _ = clean(df)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Rules are applied sequentially (no double-counting)
# ---------------------------------------------------------------------------


class TestRuleOrdering:
    def test_row_removed_by_first_rule_not_counted_again(self) -> None:
        # a_au=0 triggers rule 1 (non-finite? no — 0 is finite) then rule 2
        # e=6 is valid for rule 1, caught by rule 3
        df = _make_df(
            a_au=[0.0, 2.77, 2.67, 2.36, 2.58],
            eccentricity=[0.1, 6.0, 0.256, 0.090, 0.190],
        )
        result, removed = clean(df)
        assert len(result) == 3
        assert removed["a_au_le_zero"] == 1
        assert removed["e_ge_one"] == 1

    def test_removed_dict_has_all_rule_keys(self) -> None:
        _, removed = clean(_make_df())
        assert set(removed.keys()) == {
            "non_finite_orbital_elements",
            "a_au_le_zero",
            "e_ge_one",
        }

    def test_index_reset_after_cleaning(self) -> None:
        df = _make_df(a_au=[0.0, 2.77, 2.67, 2.36, 2.58])
        result, _ = clean(df)
        assert list(result.index) == list(range(len(result)))


# ---------------------------------------------------------------------------
# _latest_raw_csv
# ---------------------------------------------------------------------------


class TestLatestRawCsv:
    def test_returns_latest_by_name(self, tmp_path: Path) -> None:
        for name in ["sbdb_20260101.csv", "sbdb_20260201.csv", "sbdb_20260330.csv"]:
            (tmp_path / name).write_text("spkid\n1\n")
        result = _latest_raw_csv(tmp_path)
        assert result.name == "sbdb_20260330.csv"

    def test_raises_when_no_csv(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No sbdb_"):
            _latest_raw_csv(tmp_path)

    def test_ignores_non_sbdb_files(self, tmp_path: Path) -> None:
        (tmp_path / "other.csv").write_text("x\n")
        (tmp_path / "sbdb_20260330.csv").write_text("spkid\n1\n")
        result = _latest_raw_csv(tmp_path)
        assert result.name == "sbdb_20260330.csv"


# ---------------------------------------------------------------------------
# _write_metadata
# ---------------------------------------------------------------------------


class TestWriteMetadata:
    def test_creates_json_file(self, tmp_path: Path) -> None:
        _write_metadata(tmp_path, "20260330", "sbdb_20260328.csv", 1000, 990, {"a_au_le_zero": 10})
        assert (tmp_path / "sbdb_clean_20260330.metadata.json").exists()

    def test_content_is_correct(self, tmp_path: Path) -> None:
        removed = {"non_finite_orbital_elements": 0, "a_au_le_zero": 10, "e_ge_one": 5}
        _write_metadata(tmp_path, "20260330", "sbdb_20260328.csv", 1000, 985, removed)
        content = json.loads((tmp_path / "sbdb_clean_20260330.metadata.json").read_text())
        assert content["rows_in"] == 1000
        assert content["rows_out"] == 985
        assert content["rows_removed"] == 15
        assert content["removed_by_rule"] == removed

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b"
        _write_metadata(nested, "20260330", "sbdb.csv", 10, 10, {})
        assert nested.exists()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def _sample_csv(self, path: Path) -> None:
        pd.DataFrame(
            {
                "a_au": [2.77, 2.5, 0.0],
                "eccentricity": [0.079, 0.1, 0.5],
                "inclination_deg": [10.6, 5.0, 20.0],
            }
        ).to_csv(path, index=False)

    def test_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.ingest import clean_sbdb

        csv_path = tmp_path / "sbdb_20260101.csv"
        self._sample_csv(csv_path)

        monkeypatch.setattr(clean_sbdb, "_latest_raw_csv", lambda _: csv_path)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, *a, **kw: None)
        monkeypatch.setattr(clean_sbdb, "_write_metadata", lambda *a, **kw: None)

        assert clean_sbdb.main() == 0

    def test_removes_invalid_row(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.ingest import clean_sbdb

        csv_path = tmp_path / "sbdb_20260101.csv"
        self._sample_csv(csv_path)

        rows_saved: dict[str, Any] = {}

        def capture_parquet(self: pd.DataFrame, *a: Any, **kw: Any) -> None:
            rows_saved["n"] = len(self)

        monkeypatch.setattr(clean_sbdb, "_latest_raw_csv", lambda _: csv_path)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", capture_parquet)
        monkeypatch.setattr(clean_sbdb, "_write_metadata", lambda *a, **kw: None)

        clean_sbdb.main()
        assert rows_saved["n"] == 2  # a_au=0.0 row removed

    def test_missing_csv_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.ingest import clean_sbdb

        def raise_fnf(_: Path) -> Path:
            raise FileNotFoundError("no csv")

        monkeypatch.setattr(clean_sbdb, "_latest_raw_csv", raise_fnf)

        with pytest.raises(FileNotFoundError):
            clean_sbdb.main()
