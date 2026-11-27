"""
Security tests for the model server API key authentication.

Tests for timing attack resistance, rate limiting, and constant-time comparison.
"""

import hashlib
import os

# Import the model server
import sys
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from demand_forecasting.serving.model_server import APIKeyManager, app, rate_limit_cache


class TestAPIKeyManager:
    """Test the API key manager functionality."""

    def test_load_api_key_hashes(self):
        """Test loading and hashing of API keys."""
        with patch.dict(os.environ, {"VALID_API_KEYS": "key1,key2,key3"}):
            manager = APIKeyManager()
            assert len(manager.valid_key_hashes) == 3

            # Verify keys are hashed (not stored in plain text)
            for key_hash, metadata in manager.valid_key_hashes.items():
                assert key_hash not in ["key1", "key2", "key3"]  # Not plain text
                assert len(key_hash) == 64  # SHA-256 hex length
                assert "hash" in metadata
                assert "created_at" in metadata

    def test_load_empty_api_keys(self):
        """Test handling of empty API key configuration."""
        with patch.dict(os.environ, {"VALID_API_KEYS": ""}, clear=True):
            manager = APIKeyManager()
            assert len(manager.valid_key_hashes) == 0

    def test_hash_api_key(self):
        """Test API key hashing."""
        manager = APIKeyManager()
        test_key = "test_api_key_123"
        expected_hash = hashlib.sha256(test_key.encode()).hexdigest()
        assert manager._hash_api_key(test_key) == expected_hash

    def test_verify_key_constant_time_valid(self):
        """Test constant-time verification with valid key."""
        with patch.dict(os.environ, {"VALID_API_KEYS": "valid_key_123"}):
            manager = APIKeyManager()
            assert manager.verify_key_constant_time("valid_key_123") is True

    def test_verify_key_constant_time_invalid(self):
        """Test constant-time verification with invalid key."""
        with patch.dict(os.environ, {"VALID_API_KEYS": "valid_key_123"}):
            manager = APIKeyManager()
            assert manager.verify_key_constant_time("invalid_key") is False


class TestTimingAttackResistance:
    """Test resistance to timing attacks."""

    def test_constant_time_comparison_timing(self):
        """Verify that comparison takes constant time regardless of key validity."""
        with patch.dict(os.environ, {"VALID_API_KEYS": "valid_key_123"}):
            manager = APIKeyManager()

            # Test with valid and invalid keys
            valid_key = "valid_key_123"
            invalid_key = "completely_different_key_456"

            # Warm up and measure timing for valid and invalid keys
            valid_timings = []
            for _ in range(500):
                start = time.perf_counter()
                result = manager.verify_key_constant_time(valid_key)
                end = time.perf_counter()
                valid_timings.append(end - start)
                assert result is True

            invalid_timings = []
            for _ in range(500):
                start = time.perf_counter()
                result = manager.verify_key_constant_time(invalid_key)
                end = time.perf_counter()
                invalid_timings.append(end - start)
                assert result is False

            # Median timings filter OS scheduler spikes on sub-microsecond comparisons
            valid_median = sorted(valid_timings)[len(valid_timings) // 2]
            invalid_median = sorted(invalid_timings)[len(invalid_timings) // 2]
            assert abs(valid_median - invalid_median) < 1e-4

    def test_no_short_circuit_on_first_character(self):
        """Test that comparison doesn't short-circuit on first character mismatch."""
        with patch.dict(os.environ, {"VALID_API_KEYS": "valid_key_123"}):
            manager = APIKeyManager()

            # Keys that differ on first character vs last character
            key2_diff_first = "xalid_key_123"  # Different first character
            key2_diff_last = "valid_key_124"  # Different last character

            # Measure timing
            timings_first = []
            timings_last = []

            for _ in range(500):
                start = time.perf_counter()
                assert manager.verify_key_constant_time(key2_diff_first) is False
                timings_first.append(time.perf_counter() - start)

                start = time.perf_counter()
                assert manager.verify_key_constant_time(key2_diff_last) is False
                timings_last.append(time.perf_counter() - start)

            median_first = sorted(timings_first)[len(timings_first) // 2]
            median_last = sorted(timings_last)[len(timings_last) // 2]
            assert abs(median_first - median_last) < 1e-4


class TestRateLimiting:
    """Test rate limiting functionality."""

    def setup_method(self):
        """Clear rate limit cache before each test."""
        rate_limit_cache.clear()

    def test_rate_limiting_blocks_after_threshold(self):
        """Test that rate limiting blocks after threshold attempts."""
        client = TestClient(app)

        # Make 15 failed attempts (threshold is 10)
        responses = []
        for i in range(15):
            response = client.post(
                "/predict",
                headers={"X-API-Key": f"invalid_key_{i}"},
                json={
                    "features": {
                        "temp": 20.0,
                        "humidity": 50.0,
                        "wind_speed": 10.0,
                        "hour": 12,
                        "day_of_week": 3,
                    }
                },
            )
            responses.append(response)

        # First 10 should return 403 (invalid key)
        for i in range(10):
            assert responses[i].status_code == 403

        # After 10, should return 429 (rate limited)
        for i in range(10, 15):
            assert responses[i].status_code == 429
            assert "Too many authentication attempts" in responses[i].json()["detail"]

    def test_rate_limiting_resets_on_success(self):
        """Test that rate limit resets on successful authentication."""
        with patch.dict(os.environ, {"VALID_API_KEYS": "valid_key_123"}):
            client = TestClient(app)

            # Make 9 failed attempts
            for i in range(9):
                response = client.post(
                    "/predict",
                    headers={"X-API-Key": f"invalid_key_{i}"},
                    json={
                        "features": {
                            "temp": 20.0,
                            "humidity": 50.0,
                            "wind_speed": 10.0,
                            "hour": 12,
                            "day_of_week": 3,
                        }
                    },
                )
                assert response.status_code == 403

            # Make successful attempt (should fail due to missing model, but auth passes)
            response = client.post(
                "/predict",
                headers={"X-API-Key": "valid_key_123"},
                json={
                    "features": {
                        "temp": 0.5,
                        "humidity": 0.5,
                        "wind_speed": 0.2,
                        "hour": 12,
                        "day_of_week": 3,
                    }
                },
            )
            # Should fail with 503 (model not loaded), not 403/429 (auth)
            assert response.status_code == 503

            # Next failed attempt should work (rate limit reset)
            response = client.post(
                "/predict",
                headers={"X-API-Key": "another_invalid_key"},
                json={
                    "features": {
                        "temp": 20.0,
                        "humidity": 50.0,
                        "wind_speed": 10.0,
                        "hour": 12,
                        "day_of_week": 3,
                    }
                },
            )
            assert response.status_code == 403


class TestSecureLogging:
    """Test that sensitive information is not logged."""

    def test_no_key_logging_on_failure(self):
        """Test that API keys are not logged on authentication failure."""
        with patch("demand_forecasting.serving.model_server.logger") as mock_logger:
            client = TestClient(app)

            # Make failed authentication attempt
            response = client.post(
                "/predict",
                headers={"X-API-Key": "sensitive_key_12345"},
                json={
                    "features": {
                        "temp": 20.0,
                        "humidity": 50.0,
                        "wind_speed": 10.0,
                        "hour": 12,
                        "day_of_week": 3,
                    }
                },
            )

            assert response.status_code == 403

            # Check that no API key material was logged
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "Invalid API key attempt" in str(call)
            ]

            assert len(warning_calls) > 0

            # Verify no part of the API key appears in logs
            for call in warning_calls:
                log_message = str(call)
                assert "sensitive_key" not in log_message
                assert "12345" not in log_message

    def test_retry_after_header_on_rate_limit(self):
        """Test that Retry-After header is included on rate limit."""
        client = TestClient(app)

        # Make 10 failed attempts to trigger rate limit
        for i in range(10):
            client.post(
                "/predict",
                headers={"X-API-Key": f"invalid_key_{i}"},
                json={
                    "features": {
                        "temp": 20.0,
                        "humidity": 50.0,
                        "wind_speed": 10.0,
                        "hour": 12,
                        "day_of_week": 3,
                    }
                },
            )

        # 11th attempt should be rate limited
        response = client.post(
            "/predict",
            headers={"X-API-Key": "invalid_key_final"},
            json={
                "features": {
                    "temp": 20.0,
                    "humidity": 50.0,
                    "wind_speed": 10.0,
                    "hour": 12,
                    "day_of_week": 3,
                }
            },
        )

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "3600"


class TestSecurityHeaders:
    """Test security-related headers and responses."""

    def test_missing_api_key_returns_401(self):
        """Test that missing API key returns proper 401 response."""
        client = TestClient(app)

        response = client.post(
            "/predict",
            json={
                "features": {
                    "temp": 20.0,
                    "humidity": 50.0,
                    "wind_speed": 10.0,
                    "hour": 12,
                    "day_of_week": 3,
                }
            },
        )

        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_invalid_api_key_returns_403(self):
        """Test that invalid API key returns proper 403 response."""
        client = TestClient(app)

        response = client.post(
            "/predict",
            headers={"X-API-Key": "invalid_key"},
            json={
                "features": {
                    "temp": 20.0,
                    "humidity": 50.0,
                    "wind_speed": 10.0,
                    "hour": 12,
                    "day_of_week": 3,
                }
            },
        )

        assert response.status_code == 403
        assert "Invalid API key" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
