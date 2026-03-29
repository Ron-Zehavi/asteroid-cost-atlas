from pathlib import Path
import requests

from asteroid_cost_atlas.ingest.ingest_sbdb import fetch_page


class MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_page_uses_cache(tmp_path: Path, monkeypatch):
    payload = {"fields": ["spkid"], "data": [["1"]]}
    calls = {"count": 0}

    def mock_get(self, url, params, timeout):
        calls["count"] += 1
        return MockResponse(payload)

    monkeypatch.setattr(requests.Session, "get", mock_get)

    with requests.Session() as session:
        out1 = fetch_page(session, "https://example.com", ["spkid"], 10, 0, tmp_path)
        out2 = fetch_page(session, "https://example.com", ["spkid"], 10, 0, tmp_path)

    assert out1 == payload
    assert out2 == payload
    assert calls["count"] == 1