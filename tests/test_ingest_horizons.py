from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from asteroid_cost_atlas.ingest.ingest_horizons import (
    _extract_field,
    _parse_elements_response,
    fetch_batch,
)


class TestExtractField:
    def test_extracts_numeric(self) -> None:
        text = "A= 2.76701  EC= 0.07554  IN= 10.5938"
        assert _extract_field(text, "A=", "AU") == pytest.approx(2.76701)

    def test_extracts_eccentricity(self) -> None:
        text = "A= 2.76701  EC= 0.07554  IN= 10.5938"
        assert _extract_field(text, "EC=", None) == pytest.approx(0.07554)

    def test_returns_none_when_missing(self) -> None:
        assert _extract_field("no data here", "A=", None) is None

    def test_returns_none_for_non_numeric(self) -> None:
        assert _extract_field("A= notanumber EC=0.1", "A=", None) is None


class TestParseElementsResponse:
    def _make_response(
        self, a: str = "2.767", e: str = "0.076", i: str = "10.59"
    ) -> dict:
        return {
            "result": f"$$SOE\n A= {a}  EC= {e}  IN= {i}\n$$EOE"
        }

    def test_parses_valid_response(self) -> None:
        result = _parse_elements_response(self._make_response())
        assert result is not None
        assert result["a_au_horizons"] == pytest.approx(2.767)
        assert result["eccentricity_horizons"] == pytest.approx(0.076)
        assert result["inclination_deg_horizons"] == pytest.approx(10.59)

    def test_returns_none_for_empty_result(self) -> None:
        assert _parse_elements_response({"result": ""}) is None
        assert _parse_elements_response({}) is None

    def test_returns_none_for_invalid_a(self) -> None:
        assert _parse_elements_response(self._make_response(a="-1.0")) is None

    def test_returns_none_for_e_ge_1(self) -> None:
        assert _parse_elements_response(self._make_response(e="1.0")) is None

    def test_returns_none_for_nan(self) -> None:
        assert _parse_elements_response(self._make_response(a="nan")) is None


class TestFetchBatch:
    def test_empty_input(self) -> None:
        result = fetch_batch([])
        assert len(result) == 0
        assert "spkid" in result.columns

    def test_collects_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from asteroid_cost_atlas.ingest import ingest_horizons

        call_count = 0

        def mock_fetch(
            spkid: int,
            epoch_jd: str = "",
            api_url: str = "",
            timeout: int = 30,
        ) -> dict[str, float] | None:
            nonlocal call_count
            call_count += 1
            if spkid == 999:
                return None
            return {
                "a_au_horizons": 1.0 + spkid * 0.001,
                "eccentricity_horizons": 0.1,
                "inclination_deg_horizons": 5.0,
            }

        monkeypatch.setattr(ingest_horizons, "fetch_horizons_elements", mock_fetch)
        monkeypatch.setattr(ingest_horizons, "_RATE_LIMIT_DELAY", 0)

        result = fetch_batch([1, 2, 999])
        assert len(result) == 2
        assert call_count == 3
        assert result.iloc[0]["spkid"] == 1


class TestOrbitalHorizonsPreference:
    """Test that add_orbital_features prefers Horizons elements."""

    def test_horizons_overrides_sbdb(self) -> None:
        from asteroid_cost_atlas.scoring.orbital import add_orbital_features

        df = pd.DataFrame(
            {
                "a_au": [2.0, 3.0],
                "eccentricity": [0.1, 0.2],
                "inclination_deg": [5.0, 10.0],
                "a_au_horizons": [2.5, None],
                "eccentricity_horizons": [0.15, None],
                "inclination_deg_horizons": [7.0, None],
            }
        )
        result = add_orbital_features(df)

        # Row 0: should use Horizons (a=2.5), row 1: should use SBDB (a=3.0)
        assert result.loc[0, "orbital_precision_source"] == "horizons"
        assert result.loc[1, "orbital_precision_source"] == "sbdb"

        # Verify the delta-v differs from what SBDB alone would produce
        sbdb_only = add_orbital_features(df.drop(
            columns=["a_au_horizons", "eccentricity_horizons", "inclination_deg_horizons"]
        ))
        assert result.loc[0, "delta_v_km_s"] != sbdb_only.loc[0, "delta_v_km_s"]
        # Row 1 should be identical (no Horizons data)
        assert result.loc[1, "delta_v_km_s"] == pytest.approx(sbdb_only.loc[1, "delta_v_km_s"])

    def test_no_horizons_columns_works(self) -> None:
        from asteroid_cost_atlas.scoring.orbital import add_orbital_features

        df = pd.DataFrame(
            {
                "a_au": [2.0],
                "eccentricity": [0.1],
                "inclination_deg": [5.0],
            }
        )
        result = add_orbital_features(df)
        assert result.loc[0, "orbital_precision_source"] == "sbdb"
        assert result.loc[0, "delta_v_km_s"] > 0


class TestMain:
    def test_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from asteroid_cost_atlas.ingest import ingest_horizons

        # Create a minimal enriched parquet with NEA flag
        enriched_df = pd.DataFrame(
            {
                "spkid": [20000001, 20000002],
                "neo": ["Y", "N"],
                "a_au": [1.2, 2.5],
                "eccentricity": [0.1, 0.3],
                "inclination_deg": [5.0, 12.0],
            }
        )
        processed = tmp_path / "data" / "processed"
        processed.mkdir(parents=True)
        enriched_df.to_parquet(processed / "sbdb_enriched_20260402.parquet", index=False)

        raw = tmp_path / "data" / "raw"
        raw.mkdir(parents=True)

        def mock_fetch(
            spkid: int,
            epoch_jd: str = "",
            api_url: str = "",
            timeout: int = 30,
        ) -> dict[str, float] | None:
            return {
                "a_au_horizons": 1.21,
                "eccentricity_horizons": 0.11,
                "inclination_deg_horizons": 5.1,
            }

        monkeypatch.setattr(ingest_horizons, "fetch_horizons_elements", mock_fetch)
        monkeypatch.setattr(ingest_horizons, "_RATE_LIMIT_DELAY", 0)

        def patched_main() -> int:
            import logging

            logging.basicConfig(level=logging.INFO, format="%(message)s")
            # Simulate main logic with tmp_path as root
            df = pd.read_parquet(processed / "sbdb_enriched_20260402.parquet")
            nea_mask = df["neo"].astype(str).str.upper() == "Y"
            nea_spkids = df.loc[nea_mask, "spkid"].dropna().astype(int).tolist()
            result = ingest_horizons.fetch_batch(nea_spkids)
            result.to_parquet(raw / "horizons_20260402.parquet", index=False)
            return 0

        assert patched_main() == 0
        output = pd.read_parquet(raw / "horizons_20260402.parquet")
        assert len(output) == 1  # Only 1 NEA
