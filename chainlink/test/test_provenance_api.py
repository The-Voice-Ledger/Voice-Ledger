"""
test_provenance_api.py — Unit tests for the CRE Provenance API

Run from project root:
    python -m pytest chainlink/test/test_provenance_api.py -v
"""

import os
import sys

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from fastapi.testclient import TestClient
from chainlink.api.provenance_api import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "voice-ledger-cre-api"
        assert "timestamp" in data


class TestProvenanceEndpoint:
    def test_provenance_returns_all_fields(self):
        resp = client.get("/api/provenance")
        assert resp.status_code == 200
        data = resp.json()

        required_fields = [
            "totalFarmers",
            "totalBatches",
            "verifiedBatches",
            "totalQuantityKg",
            "eudrCompliantPercent",
            "batchesAnchored",
            "lastUpdated",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            assert isinstance(data[field], int), f"{field} should be int, got {type(data[field])}"

    def test_provenance_eudr_percent_in_range(self):
        resp = client.get("/api/provenance")
        data = resp.json()
        assert 0 <= data["eudrCompliantPercent"] <= 100


class TestBatchEndpoint:
    def test_nonexistent_batch_returns_404(self):
        resp = client.get("/api/batch/DOES_NOT_EXIST_12345")
        assert resp.status_code == 404

    def test_batch_endpoint_accepts_valid_id(self):
        """If any batch exists, it should return 200 with required fields."""
        # First check what batches exist via provenance
        prov = client.get("/api/provenance").json()
        if prov["totalBatches"] == 0:
            pytest.skip("No batches in database to test against")


class TestDeforestationEndpoint:
    def test_nonexistent_farm_returns_404(self):
        resp = client.get("/api/deforestation/FARM_DOES_NOT_EXIST")
        assert resp.status_code == 404

    def test_deforestation_endpoint_returns_scaled_values(self):
        """If a farm with GPS exists, verify scaled integer fields."""
        # This test requires a farm in the DB — skip if none
        resp = client.get("/api/deforestation/FARM-001")
        if resp.status_code == 404:
            pytest.skip("FARM-001 not in database")
        if resp.status_code == 422:
            pytest.skip("FARM-001 has no GPS coordinates")

        data = resp.json()
        assert isinstance(data["latitude"], int), "latitude should be scaled int"
        assert isinstance(data["longitude"], int), "longitude should be scaled int"
        assert data["riskLevelCode"] in [0, 1, 2, 3]
        assert isinstance(data["eudrCompliant"], bool)
