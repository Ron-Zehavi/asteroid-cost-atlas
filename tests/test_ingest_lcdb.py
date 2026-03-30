from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.ingest_lcdb import (
    _VALID_U_CODES,
    add_spkid,
    filter_quality,
    parse_summary,
)


def _make_lcdb_df(**overrides: list) -> pd.DataFrame:
    """Build a minimal LCDB-like DataFrame."""
    base: dict = {
        "number": [1, 2, 3, 4, 5],
        "name": ["Ceres", "Pallas", "Juno", "Vesta", "Astraea"],
        "designation": ["A801 AA", "A802 FA", "A804 RA", "A807 FA", "A845 AB"],
        "family": ["", "", "", "", ""],
        "taxonomy": ["C", "B", "S", "V", "S"],
        "lcdb_diameter_km": [939.4, 513.0, 246.6, 522.8, 119.1],
        "lcdb_h": [3.53, 4.13, 5.33, 3.20, 6.85],
        "lcdb_albedo": [0.09, 0.16, 0.21, 0.42, 0.27],
        "period_flag": ["", "", "", "", ""],
        "lcdb_rotation_hours": [9.07, 7.81, 7.21, 5.34, 16.8],
        "u_quality": ["3", "3", "2+", "3", "2-"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


class TestFilterQuality:
    def test_keeps_valid_codes(self) -> None:
        df = _make_lcdb_df(u_quality=["3", "2", "1", "2-", "1+"])
        result = filter_quality(df)
        assert len(result) == 3  # 3, 2, 2-

    def test_all_valid(self) -> None:
        df = _make_lcdb_df()
        result = filter_quality(df)
        assert len(result) == 5

    def test_resets_index(self) -> None:
        df = _make_lcdb_df(u_quality=["3", "1", "1", "1", "1"])
        result = filter_quality(df)
        assert list(result.index) == [0]

    def test_valid_codes_match(self) -> None:
        for code in ("2-", "2", "2+", "3-", "3"):
            assert code in _VALID_U_CODES


class TestAddSpkid:
    def test_numbered_objects_get_spkid(self) -> None:
        df = _make_lcdb_df()
        result = add_spkid(df)
        assert result.loc[0, "spkid"] == 20_000_001

    def test_unnumbered_objects_dropped(self) -> None:
        df = _make_lcdb_df(number=[1, None, 3, None, 5])
        result = add_spkid(df)
        assert len(result) == 3

    def test_spkid_is_int(self) -> None:
        df = _make_lcdb_df()
        result = add_spkid(df)
        assert result["spkid"].dtype in (int, "int64")


class TestParseSummary:
    def _make_zip(self, tmp_path: Path) -> bytes:
        """Create a minimal ZIP with a fake lc_summary_pub.txt."""
        import io
        import zipfile

        # Build a minimal fixed-width file with 4 header lines + 1 data row
        lines = [
            "LCDB Summary Table",
            "Date: 2023-10-01",
            "Number  * Name                          Designation         Family  "
            " CS Class      DS DF Diam     HS H      HB GS G      G1     G2     "
            "AS AF Albedo PF Period         PDescrip        AF AMin AMax U  Notes "
            "Bin Pol Surv  ExN Prv",
            "-" * 217,
            "      1   1 Ceres (A801 AA)              A801 AA             "
            "   C  C          S     939.400  J   3.530     J  0.120               "
            "S    0.0900      9.07417000                    0.04 0.04 3        "
            "        Y                ",
        ]
        content = "\r\n".join(lines) + "\r\n"

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("lc_summary_pub.txt", content)
        return buf.getvalue()

    def test_parses_one_row(self, tmp_path: Path) -> None:
        zip_bytes = self._make_zip(tmp_path)
        df = parse_summary(zip_bytes)
        assert len(df) >= 1

    def test_number_is_numeric(self, tmp_path: Path) -> None:
        zip_bytes = self._make_zip(tmp_path)
        df = parse_summary(zip_bytes)
        assert pd.api.types.is_numeric_dtype(df["number"])


class TestMain:
    def test_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from asteroid_cost_atlas.ingest import ingest_lcdb

        df = _make_lcdb_df()

        # Mock download + parse
        monkeypatch.setattr(
            ingest_lcdb, "download_lcdb_zip", lambda **kw: b"fake"
        )
        monkeypatch.setattr(ingest_lcdb, "parse_summary", lambda _: df)
        monkeypatch.setattr(
            pd.DataFrame, "to_parquet", lambda self, *a, **kw: None
        )

        assert ingest_lcdb.main() == 0
