from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.ingest_spectral import (
    _find_column,
    add_spkid,
    classify_from_sdss_colors,
    parse_sdss_moc,
)


def _make_csv_bytes(**overrides: list) -> bytes:
    """Build minimal SDSS MOC-like CSV bytes."""
    base: dict = {
        "number": [1, 2, 3, 4, 5],
        "g": [14.5, 15.2, 13.8, 16.1, 14.9],
        "r": [14.0, 14.6, 13.3, 15.5, 14.3],
        "i": [13.9, 14.5, 13.2, 15.4, 14.2],
        "z": [13.8, 14.4, 13.1, 15.3, 14.1],
    }
    base.update(overrides)
    df = pd.DataFrame(base)
    return df.to_csv(index=False).encode("utf-8")


class TestParseSdssMoc:
    def test_parses_all_rows(self) -> None:
        raw = _make_csv_bytes()
        result = parse_sdss_moc(raw)
        assert len(result) == 5

    def test_computes_color_gr(self) -> None:
        raw = _make_csv_bytes()
        result = parse_sdss_moc(raw)
        assert "color_gr" in result.columns
        # g - r for row 0: 14.5 - 14.0 = 0.5
        assert result.loc[0, "color_gr"] == pytest.approx(0.5)

    def test_computes_color_ri(self) -> None:
        raw = _make_csv_bytes()
        result = parse_sdss_moc(raw)
        assert "color_ri" in result.columns
        # r - i for row 0: 14.0 - 13.9 = 0.1
        assert result.loc[0, "color_ri"] == pytest.approx(0.1)

    def test_computes_color_iz(self) -> None:
        raw = _make_csv_bytes()
        result = parse_sdss_moc(raw)
        assert "color_iz" in result.columns

    def test_drops_rows_without_number(self) -> None:
        raw = _make_csv_bytes(number=[1, None, 3, None, 5])
        result = parse_sdss_moc(raw)
        assert len(result) == 3

    def test_deduplicates_by_number(self) -> None:
        raw = _make_csv_bytes(
            number=[1, 1, 2, 3, 3],
            g=[14.5, 15.0, 14.0, 13.5, 16.0],
            r=[14.0, 14.5, 13.5, 13.0, 15.5],
            i=[13.9, 14.4, 13.4, 12.9, 15.4],
            z=[13.8, 14.3, 13.3, 12.8, 15.3],
        )
        result = parse_sdss_moc(raw)
        assert len(result) == 3

    def test_number_is_int(self) -> None:
        raw = _make_csv_bytes()
        result = parse_sdss_moc(raw)
        assert result["number"].dtype in (int, "int64")


class TestClassifyFromSdssColors:
    def test_c_type(self) -> None:
        # Low g-r, low r-i
        assert classify_from_sdss_colors(0.40, 0.05) == "C"

    def test_s_type_red(self) -> None:
        # High g-r, moderate r-i
        assert classify_from_sdss_colors(0.55, 0.10) == "S"

    def test_v_type(self) -> None:
        # Low g-r, higher r-i
        assert classify_from_sdss_colors(0.40, 0.15) == "V"

    def test_nan_returns_u(self) -> None:
        assert classify_from_sdss_colors(float("nan"), 0.1) == "U"
        assert classify_from_sdss_colors(0.5, float("nan")) == "U"

    def test_inf_returns_u(self) -> None:
        assert classify_from_sdss_colors(float("inf"), 0.1) == "U"

    def test_s_type_moderate(self) -> None:
        # g-r >= 0.50, r-i < 0.20
        assert classify_from_sdss_colors(0.52, 0.08) == "S"


class TestFindColumn:
    def test_finds_exact_match(self) -> None:
        df = pd.DataFrame({"number": [1], "g": [14.0]})
        assert _find_column(df, ["number"]) == "number"

    def test_case_insensitive(self) -> None:
        df = pd.DataFrame({"Number": [1]})
        assert _find_column(df, ["number"]) == "Number"

    def test_returns_none(self) -> None:
        df = pd.DataFrame({"foo": [1]})
        assert _find_column(df, ["bar"]) is None


class TestAddSpkid:
    def test_numbered_objects_get_spkid(self) -> None:
        df = pd.DataFrame({"number": [1, 2], "color_gr": [0.5, 0.4]})
        result = add_spkid(df)
        assert result.loc[0, "spkid"] == 20_000_001

    def test_spkid_is_int(self) -> None:
        df = pd.DataFrame({"number": [1], "color_gr": [0.5]})
        result = add_spkid(df)
        assert result["spkid"].dtype in (int, "int64")


class TestMain:
    def test_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from asteroid_cost_atlas.ingest import ingest_spectral

        raw = _make_csv_bytes()
        monkeypatch.setattr(ingest_spectral, "download_sdss_moc", lambda **kw: raw)
        monkeypatch.setattr(
            pd.DataFrame, "to_parquet", lambda self, *a, **kw: None
        )

        assert ingest_spectral.main() == 0
