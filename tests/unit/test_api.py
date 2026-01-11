"""
Tests for API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "VGAP" in data["name"]


class TestAuthEndpoints:
    """Tests for authentication endpoints."""
    
    def test_login_success(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "admin@vgap.local",
            "password": "admin_dev_password"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "admin@vgap.local",
            "password": "wrong_password"
        })
        assert response.status_code == 401


class TestRunEndpoints:
    """Tests for run management endpoints."""
    
    def test_create_run_unauthorized(self, client):
        response = client.post("/api/v1/runs", json={
            "name": "Test Run",
            "mode": "amplicon",
            "primer_scheme": "ARTIC_v4",
            "samples": []
        })
        assert response.status_code == 401
    
    def test_create_run_authorized(self, authenticated_client):
        response = authenticated_client.post("/api/v1/runs", json={
            "name": "Test Run",
            "mode": "amplicon",
            "primer_scheme": "ARTIC_v4",
            "samples": [{
                "metadata": {
                    "sample_id": "TEST001",
                    "collection_date": "2024-01-15",
                    "host": "human",
                    "location": "US",
                    "protocol": "amplicon",
                    "platform": "Illumina",
                    "run_id": "RUN001",
                    "batch_id": "BATCH001",
                },
                "r1_filename": "TEST001_R1.fastq.gz",
                "r2_filename": "TEST001_R2.fastq.gz",
            }]
        })
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
    
    def test_list_runs(self, authenticated_client):
        response = authenticated_client.get("/api/v1/runs")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


@pytest.fixture
def client():
    """Create test client."""
    from vgap.api.main import app
    return TestClient(app)


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client."""
    # Get token
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@vgap.local",
        "password": "admin_dev_password"
    })
    token = response.json()["access_token"]
    
    # Add auth header
    client.headers["Authorization"] = f"Bearer {token}"
    return client
