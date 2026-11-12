import pytest
from app.core.config import settings


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "SeatSurge"
    assert data["version"] == "0.1.0"
    assert "instance_id" in data
    assert "X-Backend-Instance" in response.headers
    assert "X-Process-Time-Ms" in response.headers


def test_direct_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["ok", "degraded", "down"]
    assert "instance_id" in data
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]


def test_api_v1_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data


def test_health_liveness_endpoint(client):
    response = client.get("/api/v1/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "instance_id" in data


def test_health_readiness_endpoint(client):
    response = client.get("/api/v1/health/readiness")
    # In an isolated unit test where Postgres/Redis aren't active, readiness returns 503
    assert response.status_code in [200, 503]
    data = response.json()
    assert "ready" in data
    assert "database" in data
    assert "redis" in data


def test_settings_configuration():
    assert settings.PROJECT_NAME == "SeatSurge"
    assert settings.TOTAL_SEATS == 5040
    assert settings.HOLD_DURATION_SECONDS == 120
    assert settings.MAX_GROUP_SEATS == 6
