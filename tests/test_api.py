"""Tests for the FastAPI REST API."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from asteroid_cost_atlas.api.app import app
from asteroid_cost_atlas.utils.query import CostAtlasDB


@pytest.fixture()
def _atlas_parquet(tmp_path: Path) -> Path:
    """Create a minimal atlas parquet for testing."""
    df = pd.DataFrame(
        {
            "spkid": [20000001, 20000002, 20000003, 20000004, 20000005],
            "name": [
                "1 Ceres", "2 Pallas", "3 Juno", "4 Vesta", "5 Astraea",
            ],
            "a_au": [2.77, 2.77, 2.67, 2.36, 2.57],
            "eccentricity": [0.076, 0.231, 0.256, 0.089, 0.191],
            "inclination_deg": [10.6, 34.8, 13.0, 7.1, 5.4],
            "long_asc_node_deg": [80.3, 173.0, 169.9, 103.8, 141.6],
            "arg_perihelion_deg": [73.6, 310.1, 248.4, 149.9, 358.9],
            "mean_anomaly_deg": [77.4, 78.2, 248.7, 20.9, 196.5],
            "epoch_mjd": [60400.0, 60400.0, 60400.0, 60400.0, 60400.0],
            "abs_magnitude": [3.53, 4.13, 5.33, 3.20, 6.85],
            "diameter_km": [939.4, 513.0, 246.6, 522.8, 119.1],
            "diameter_estimated_km": [939.4, 513.0, 246.6, 522.8, 119.1],
            "diameter_source": ["measured"] * 5,
            "rotation_hours": [9.07, 7.81, 7.21, 5.34, 16.8],
            "albedo": [0.09, 0.16, 0.21, 0.42, 0.27],
            "neo": ["N", "N", "N", "N", "N"],
            "pha": ["N", "N", "N", "N", "N"],
            "orbit_class": ["MBA", "MBA", "MBA", "MBA", "MBA"],
            "moid_au": [1.59, 1.23, 1.04, 1.14, 0.95],
            "spectral_type": ["C", "B", "S", "V", "S"],
            "delta_v_km_s": [8.5, 10.2, 9.1, 7.8, 8.9],
            "tisserand_jupiter": [3.31, 3.12, 3.28, 3.41, 3.33],
            "inclination_penalty": [0.002, 0.089, 0.013, 0.004, 0.002],
            "orbital_precision_source": ["sbdb"] * 5,
            "surface_gravity_m_s2": [0.28, 0.22, 0.10, 0.25, 0.04],
            "composition_class": ["C", "C", "S", "V", "S"],
            "composition_source": ["taxonomy"] * 5,
            "resource_value_usd_per_kg": [49.96, 49.96, 7.27, 3.76, 7.27],
            "specimen_value_per_kg": [90000.0] * 5,
            "estimated_mass_kg": [9.4e20, 2.1e20, 2.7e19, 2.6e20, 2.0e18],
            "mission_cost_usd_per_kg": [1e9, 2e9, 1.5e9, 8e8, 1.2e9],
            "margin_per_kg": [-1e9, -2e9, -1.5e9, 5000.0, -1.2e9],
            "break_even_kg": [None, None, None, 60000.0, None],
            "is_viable": [False, False, False, True, False],
            "missions_supported": [0.0, 0.0, 0.0, 5.0, 0.0],
            "mission_revenue_usd": [0.0, 0.0, 0.0, 9e7, 0.0],
            "mission_cost_usd": [0.0, 0.0, 0.0, 6e7, 0.0],
            "mission_profit_usd": [0.0, 0.0, 0.0, 3e7, 0.0],
            "campaign_revenue_usd": [0.0, 0.0, 0.0, 4.5e8, 0.0],
            "campaign_cost_usd": [0.0, 0.0, 0.0, 3e8, 0.0],
            "campaign_profit_usd": [0.0, 0.0, 0.0, 1.5e8, 0.0],
            "economic_score": [0.0, 0.0, 0.0, 100.0, 0.0],
            "economic_priority_rank": [2, 4, 3, 1, 5],
            "accessibility": [0.01, 0.01, 0.01, 0.02, 0.01],
            "total_extractable_precious_kg": [0.0, 0.0, 0.0, 1e6, 0.0],
            "total_precious_value_usd": [0.0, 0.0, 0.0, 9e10, 0.0],
        }
    )
    path = tmp_path / "atlas_20260402.parquet"
    df.to_parquet(path, index=False, engine="pyarrow")
    return path


@pytest.fixture()
def client(_atlas_parquet: Path) -> TestClient:
    """TestClient with a mock atlas loaded."""
    app.state.db = CostAtlasDB(_atlas_parquet)
    client = TestClient(app)
    yield client  # type: ignore[misc]
    app.state.db.close()


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestStats:
    def test_stats_returns_summary(self, client: TestClient) -> None:
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_objects"] == 5
        assert data["scored_objects"] == 5

    def test_delta_v_histogram(self, client: TestClient) -> None:
        resp = client.get("/api/charts/delta-v?bin_width=2.0")
        assert resp.status_code == 200
        bins = resp.json()
        assert len(bins) > 0
        assert "bin_floor_km_s" in bins[0]

    def test_composition_distribution(self, client: TestClient) -> None:
        resp = client.get("/api/charts/composition")
        assert resp.status_code == 200
        data = resp.json()
        classes = {r["class"] for r in data}
        assert "C" in classes


class TestAsteroids:
    def test_list_default(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["data"]) == 5

    def test_list_filter_viable(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids?is_viable=true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["name"] == "4 Vesta"

    def test_list_filter_composition(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids?composition_class=C")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_sort(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids?sort=delta_v_km_s&order=asc")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data[0]["delta_v_km_s"] <= data[-1]["delta_v_km_s"]

    def test_list_pagination(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids?limit=2&offset=2")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["total"] == 5

    def test_list_invalid_sort(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids?sort=INVALID")
        assert resp.status_code == 400

    def test_get_by_spkid(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids/20000001")
        assert resp.status_code == 200
        assert resp.json()["name"] == "1 Ceres"

    def test_get_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids/99999999")
        assert resp.status_code == 404

    def test_top_accessible(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids/top?n=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["delta_v_km_s"] <= data[1]["delta_v_km_s"]

    def test_nea_candidates(self, client: TestClient) -> None:
        resp = client.get("/api/asteroids/nea")
        assert resp.status_code == 200


class TestSearch:
    def test_search_by_name(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=Ceres")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "Ceres" in data[0]["name"]

    def test_search_no_results(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=ZZZZNOTFOUND")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_search_requires_query(self, client: TestClient) -> None:
        resp = client.get("/api/search")
        assert resp.status_code == 422
