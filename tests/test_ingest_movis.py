from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.ingest_movis import (
    add_spkid,
    parse_movis,
)


def _make_movis_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Number": ["1", "2", "3", "4", "5"],
            "Y-J": [0.30, 0.38, 0.32, 0.40, None],
            "J-Ks": [0.35, 0.55, 0.42, 0.60, None],
            "H-Ks": [0.14, 0.20, 0.17, 0.25, None],
            "ClassFin": ["C", "S", "X", "V", None],
        }
    )


class TestParseMovis:
    def test_parses_all_rows_with_data(self) -> None:
        result = parse_movis(_make_movis_df())
        # Row 5 has no colors → dropped
        assert len(result) == 4

    def test_column_names(self) -> None:
        result = parse_movis(_make_movis_df())
        assert "number" in result.columns
        assert "movis_yj" in result.columns
        assert "movis_jks" in result.columns
        assert "movis_taxonomy" in result.columns

    def test_number_is_int(self) -> None:
        result = parse_movis(_make_movis_df())
        assert result["number"].dtype in (int, "int64")

    def test_taxonomy_preserved(self) -> None:
        result = parse_movis(_make_movis_df())
        assert result.iloc[0]["movis_taxonomy"] == "C"

    def test_deduplicates(self) -> None:
        df = _make_movis_df()
        df = pd.concat([df, df.iloc[:1]], ignore_index=True)
        result = parse_movis(df)
        assert result["number"].nunique() == len(result)


class TestAddSpkid:
    def test_spkid_computed(self) -> None:
        df = parse_movis(_make_movis_df())
        result = add_spkid(df)
        assert result.loc[0, "spkid"] == 20_000_001

    def test_spkid_is_int(self) -> None:
        df = parse_movis(_make_movis_df())
        result = add_spkid(df)
        assert result["spkid"].dtype in (int, "int64")


class TestMain:
    def test_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from asteroid_cost_atlas.ingest import ingest_movis

        df = _make_movis_df()
        monkeypatch.setattr(ingest_movis, "download_movis", lambda **kw: df)
        monkeypatch.setattr(
            pd.DataFrame, "to_parquet", lambda self, *a, **kw: None
        )
        assert ingest_movis.main() == 0
