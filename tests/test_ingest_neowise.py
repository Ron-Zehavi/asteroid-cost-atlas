from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.ingest_neowise import (
    _find_column,
    add_spkid,
    parse_neowise,
)


def _make_csv_bytes(**overrides: list) -> bytes:
    """Build minimal NEOWISE-like CSV bytes."""
    base: dict = {
        "number": [1, 2, 3, 4, 5],
        "diameter": [939.4, 513.0, 246.6, 522.8, 119.1],
        "albedo": [0.09, 0.16, 0.21, 0.42, 0.27],
    }
    base.update(overrides)
    df = pd.DataFrame(base)
    return df.to_csv(index=False).encode("utf-8")


class TestParseNeowise:
    def test_parses_all_rows(self) -> None:
        raw = _make_csv_bytes()
        result = parse_neowise(raw)
        assert len(result) == 5

    def test_column_names(self) -> None:
        raw = _make_csv_bytes()
        result = parse_neowise(raw)
        assert "neowise_diameter_km" in result.columns
        assert "neowise_albedo" in result.columns
        assert "number" in result.columns

    def test_drops_rows_without_number(self) -> None:
        raw = _make_csv_bytes(number=[1, None, 3, None, 5])
        result = parse_neowise(raw)
        assert len(result) == 3

    def test_drops_negative_diameter(self) -> None:
        raw = _make_csv_bytes(diameter=[10.0, -1.0, 5.0, 3.0, 2.0])
        result = parse_neowise(raw)
        assert (result["neowise_diameter_km"] > 0).all()

    def test_drops_negative_albedo(self) -> None:
        raw = _make_csv_bytes(albedo=[0.1, -0.05, 0.2, 0.3, 0.15])
        result = parse_neowise(raw)
        assert (result["neowise_albedo"] > 0).all()

    def test_deduplicates_by_number(self) -> None:
        raw = _make_csv_bytes(
            number=[1, 1, 2, 3, 3],
            diameter=[100.0, 200.0, 50.0, 30.0, 10.0],
            albedo=[0.1, 0.2, 0.3, 0.4, 0.5],
        )
        result = parse_neowise(raw)
        assert len(result) == 3
        # Should keep the row with the largest diameter for dups
        row1 = result[result["number"] == 1].iloc[0]
        assert row1["neowise_diameter_km"] == pytest.approx(200.0)

    def test_handles_nan_diameter_with_valid_albedo(self) -> None:
        raw = _make_csv_bytes(
            number=[1, 2],
            diameter=[None, 50.0],
            albedo=[0.1, 0.2],
        )
        result = parse_neowise(raw)
        assert len(result) == 2

    def test_drops_rows_with_neither_measurement(self) -> None:
        raw = _make_csv_bytes(
            number=[1, 2, 3, 4, 5],
            diameter=[10.0, None, 5.0, None, 2.0],
            albedo=[0.1, None, 0.2, None, 0.15],
        )
        result = parse_neowise(raw)
        assert len(result) == 3

    def test_number_is_int(self) -> None:
        raw = _make_csv_bytes()
        result = parse_neowise(raw)
        assert result["number"].dtype in (int, "int64")


class TestFindColumn:
    def test_finds_exact_match(self) -> None:
        df = pd.DataFrame({"diameter": [1], "albedo": [0.1]})
        assert _find_column(df, ["diameter"]) == "diameter"

    def test_case_insensitive(self) -> None:
        df = pd.DataFrame({"Diameter": [1], "Albedo": [0.1]})
        assert _find_column(df, ["diameter"]) == "Diameter"

    def test_returns_none_when_not_found(self) -> None:
        df = pd.DataFrame({"foo": [1]})
        assert _find_column(df, ["bar", "baz"]) is None

    def test_returns_first_match(self) -> None:
        df = pd.DataFrame({"diam": [1], "diameter": [2]})
        assert _find_column(df, ["diameter", "diam"]) == "diameter"


class TestAddSpkid:
    def test_numbered_objects_get_spkid(self) -> None:
        df = pd.DataFrame({"number": [1, 2, 3], "neowise_diameter_km": [10, 20, 30]})
        result = add_spkid(df)
        assert result.loc[0, "spkid"] == 20_000_001

    def test_unnumbered_objects_dropped(self) -> None:
        df = pd.DataFrame({"number": [1, None, 3], "neowise_diameter_km": [10, 20, 30]})
        result = add_spkid(df)
        assert len(result) == 2

    def test_spkid_is_int(self) -> None:
        df = pd.DataFrame({"number": [1], "neowise_diameter_km": [10.0]})
        result = add_spkid(df)
        assert result["spkid"].dtype in (int, "int64")


class TestMain:
    def test_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from asteroid_cost_atlas.ingest import ingest_neowise

        raw = _make_csv_bytes()
        monkeypatch.setattr(ingest_neowise, "download_neowise", lambda **kw: raw)
        monkeypatch.setattr(
            pd.DataFrame, "to_parquet", lambda self, *a, **kw: None
        )

        assert ingest_neowise.main() == 0
