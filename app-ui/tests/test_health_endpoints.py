"""Tests for health check endpoints in the UI application."""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client():
    """Create a test client for the Flask server."""
    from app import server

    server.config["TESTING"] = True
    with server.test_client() as client:
        yield client


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def test_health_endpoint_returns_200(self, client):
        """Test that /health endpoint returns 200 status."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, client):
        """Test that /health endpoint returns valid JSON."""
        response = client.get("/health")
        data = response.get_json()

        assert data is not None
        assert "status" in data
        assert "service" in data
        assert "timestamp" in data

    def test_health_endpoint_service_name(self, client):
        """Test that /health returns correct service name."""
        response = client.get("/health")
        data = response.get_json()

        assert data["service"] == "demand-forecasting-ui"

    def test_health_endpoint_status_healthy(self, client):
        """Test that /health returns healthy status."""
        response = client.get("/health")
        data = response.get_json()

        assert data["status"] == "healthy"

    def test_ready_endpoint_returns_valid_response(self, client):
        """Test that /ready endpoint returns valid response."""
        response = client.get("/ready")
        # Can be 200 (ready) or 503 (not ready)
        assert response.status_code in [200, 503]

    def test_ready_endpoint_returns_json(self, client):
        """Test that /ready endpoint returns valid JSON."""
        response = client.get("/ready")
        data = response.get_json()

        assert data is not None
        assert "ready" in data
        assert "checks" in data
        assert "timestamp" in data

    def test_ready_endpoint_includes_checks(self, client):
        """Test that /ready includes required checks."""
        response = client.get("/ready")
        data = response.get_json()

        assert "data_loaded" in data["checks"]
        assert "no_errors" in data["checks"]

    def test_metrics_endpoint_returns_200(self, client):
        """Test that /metrics endpoint returns 200 status."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_returns_prometheus_text(self, client):
        """Test that /metrics endpoint returns Prometheus exposition metrics."""
        response = client.get("/metrics")
        body = response.get_data(as_text=True)

        assert response.mimetype == "text/plain"
        assert "dash_app_memory_bytes" in body
        assert "dash_app_cpu_percent" in body


class TestAppState:
    """Test suite for application state management."""

    def test_app_state_exists(self):
        """Test that app_state dictionary exists."""
        from app import app_state

        assert isinstance(app_state, dict)

    def test_app_state_has_required_keys(self):
        """Test that app_state has required keys."""
        from app import app_state

        required_keys = ["data_loaded", "startup_time", "error"]
        for key in required_keys:
            assert key in app_state, f"Missing key: {key}"

    def test_app_state_startup_time_is_valid(self):
        """Test that startup_time is a valid ISO timestamp."""
        from datetime import datetime

        from app import app_state

        # Should not raise an exception
        datetime.fromisoformat(app_state["startup_time"])
