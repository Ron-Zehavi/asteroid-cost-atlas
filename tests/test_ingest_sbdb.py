from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from asteroid_cost_atlas.ingest.ingest_sbdb import (
    fetch_all_pages,
    fetch_page,
    to_dataframe,
    write_metadata,
)


class MockResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


# ---------------------------------------------------------------------------
# fetch_page
# ---------------------------------------------------------------------------


def test_fetch_page_uses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"fields": ["spkid"], "data": [["1"]]}
    calls = {"count": 0}

    def mock_get(self: requests.Session, url: str, params: dict, timeout: int) -> MockResponse:
        calls["count"] += 1
        return MockResponse(payload)

    monkeypatch.setattr(requests.Session, "get", mock_get)

    with requests.Session() as session:
        out1 = fetch_page(session, "https://example.com", ["spkid"], 10, 0, tmp_path)
        out2 = fetch_page(session, "https://example.com", ["spkid"], 10, 0, tmp_path)

    assert out1 == payload
    assert out2 == payload
    assert calls["count"] == 1


def test_fetch_page_writes_cache_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"fields": ["spkid"], "data": [["1"]]}

    def mock_get(self: requests.Session, url: str, params: dict, timeout: int) -> MockResponse:
        return MockResponse(payload)

    monkeypatch.setattr(requests.Session, "get", mock_get)

    with requests.Session() as session:
        fetch_page(session, "https://example.com", ["spkid"], 10, 0, tmp_path)

    cache_files = list(tmp_path.glob("*.json"))
    assert len(cache_files) == 1
    assert json.loads(cache_files[0].read_text()) == payload


# ---------------------------------------------------------------------------
# fetch_all_pages
# ---------------------------------------------------------------------------


def test_fetch_all_pages_single_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fields = ["spkid", "a_au"]
    page = {"fields": fields, "data": [["1", "2.5"], ["2", "3.1"]]}

    def mock_get(self: requests.Session, url: str, params: dict, timeout: int) -> MockResponse:
        return MockResponse(page)

    monkeypatch.setattr(requests.Session, "get", mock_get)

    with requests.Session() as session:
        result = fetch_all_pages(session, "https://example.com", fields, 10, tmp_path)

    assert result["fields"] == fields
    assert len(result["data"]) == 2


def test_fetch_all_pages_paginates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fields = ["spkid"]
    full_page = {"fields": fields, "data": [["1"], ["2"]]}
    empty_page = {"fields": fields, "data": []}
    call_count = {"n": 0}

    def mock_get(self: requests.Session, url: str, params: dict, timeout: int) -> MockResponse:
        call_count["n"] += 1
        return MockResponse(full_page if call_count["n"] == 1 else empty_page)

    monkeypatch.setattr(requests.Session, "get", mock_get)

    with requests.Session() as session:
        result = fetch_all_pages(session, "https://example.com", fields, 2, tmp_path)

    assert len(result["data"]) == 2
    assert call_count["n"] == 2


def test_fetch_all_pages_field_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def mock_get(self: requests.Session, url: str, params: dict, timeout: int) -> MockResponse:
        return MockResponse({"fields": ["wrong"], "data": [["1"]]})

    monkeypatch.setattr(requests.Session, "get", mock_get)

    with requests.Session() as session:
        with pytest.raises(ValueError, match="differ from requested"):
            fetch_all_pages(session, "https://example.com", ["spkid"], 10, tmp_path)


# ---------------------------------------------------------------------------
# to_dataframe
# ---------------------------------------------------------------------------


_FULL_FIELDS = ["spkid", "full_name", "a", "e", "i", "diameter", "rot_per", "albedo"]
_FULL_ROW = ["1", "Ceres", "2.77", "0.079", "10.6", "939.4", "9.07", "0.09"]


def test_to_dataframe_renames_columns() -> None:
    payload = {"fields": _FULL_FIELDS, "data": [_FULL_ROW]}
    df = to_dataframe(payload)
    assert "a_au" in df.columns
    assert "eccentricity" in df.columns
    assert "inclination_deg" in df.columns
    assert "name" in df.columns


def test_to_dataframe_numeric_coercion() -> None:
    payload = {"fields": _FULL_FIELDS, "data": [_FULL_ROW]}
    df = to_dataframe(payload)
    assert df["a_au"].dtype == float
    assert df["eccentricity"].dtype == float


def test_to_dataframe_drops_missing_orbital() -> None:
    bad_row = ["2", "Bad", None, "0.1", "5.0", None, None, None]
    payload = {"fields": _FULL_FIELDS, "data": [_FULL_ROW, bad_row]}
    df = to_dataframe(payload)
    assert len(df) == 1


# ---------------------------------------------------------------------------
# write_metadata
# ---------------------------------------------------------------------------


def test_write_metadata_creates_file(tmp_path: Path) -> None:
    metadata_path = tmp_path / "sbdb_20260330.metadata.json"
    write_metadata(metadata_path, "20260330", "https://example.com", ["spkid"], 100)
    assert metadata_path.exists()


def test_write_metadata_content(tmp_path: Path) -> None:
    metadata_path = tmp_path / "sbdb_20260330.metadata.json"
    write_metadata(metadata_path, "20260330", "https://example.com", ["spkid", "a"], 42)
    content = json.loads(metadata_path.read_text())
    assert content["run_date"] == "20260330"
    assert content["source_url"] == "https://example.com"
    assert content["sbdb_fields"] == ["spkid", "a"]
    assert content["record_count"] == 42


def test_write_metadata_creates_parent_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "meta.json"
    write_metadata(nested, "20260330", "https://example.com", ["spkid"], 1)
    assert nested.exists()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


_FIELDS = ["spkid", "full_name", "a", "e", "i", "diameter", "rot_per", "albedo"]
_PAYLOAD = {
    "fields": _FIELDS,
    "data": [["20000001", "Ceres", "2.77", "0.079", "10.6", "939.4", "9.07", "0.09"]],
}


def test_main_returns_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from asteroid_cost_atlas.ingest import ingest_sbdb

    config = MagicMock()
    config.base_url = "https://example.com"
    config.sbdb_fields = _FIELDS
    config.page_size = 10
    config.csv_dir = tmp_path
    config.cache_dir = tmp_path / "cache"
    config.metadata_dir = tmp_path / "metadata"
    config.raw_json_path = MagicMock()

    monkeypatch.setattr(ingest_sbdb, "load_resolved_config", lambda *a, **kw: config)
    monkeypatch.setattr(ingest_sbdb, "fetch_all_pages", lambda *a, **kw: _PAYLOAD)
    monkeypatch.setattr(
        ingest_sbdb,
        "parse_args",
        lambda *a, **kw: argparse.Namespace(page_size=10, output=tmp_path),
    )

    assert ingest_sbdb.main() == 0


def test_main_writes_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from asteroid_cost_atlas.ingest import ingest_sbdb

    config = MagicMock()
    config.base_url = "https://example.com"
    config.sbdb_fields = _FIELDS
    config.page_size = 10
    config.csv_dir = tmp_path
    config.cache_dir = tmp_path / "cache"
    config.metadata_dir = tmp_path / "metadata"
    config.raw_json_path = MagicMock()

    monkeypatch.setattr(ingest_sbdb, "load_resolved_config", lambda *a, **kw: config)
    monkeypatch.setattr(ingest_sbdb, "fetch_all_pages", lambda *a, **kw: _PAYLOAD)
    monkeypatch.setattr(
        ingest_sbdb,
        "parse_args",
        lambda *a, **kw: argparse.Namespace(page_size=10, output=tmp_path),
    )

    ingest_sbdb.main()
    assert len(list(tmp_path.glob("sbdb_*.csv"))) == 1
