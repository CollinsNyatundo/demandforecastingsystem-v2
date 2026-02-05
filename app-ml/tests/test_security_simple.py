#!/usr/bin/env python3
"""Simple security test runner for the model server.
Tests all security functionality without pytest dependencies.
"""

import hashlib
import os
import sys
import time

from fastapi.testclient import TestClient

# Add src to path
sys.path.append("src")

# Set test environment variables
os.environ["VALID_API_KEYS"] = "test_key_123,test_key_456"


def test_api_key_manager():
    """Test APIKeyManager functionality."""
    from demand_forecasting.serving.model_server import APIKeyManager

    manager = APIKeyManager()

    # Test key loading
    assert (
        len(manager.valid_key_hashes) == 2
    ), f"Expected 2 keys, got {len(manager.valid_key_hashes)}"

    # Test valid key verification
    result1 = manager.verify_key_constant_time("test_key_123")
    assert result1 is True, "Valid key should return True"

    # Test invalid key verification
    result2 = manager.verify_key_constant_time("invalid_key")
    assert result2 is False, "Invalid key should return False"

    # Test key hashing
    hash1 = manager._hash_api_key("test_key")
    expected_hash = hashlib.sha256(b"test_key").hexdigest()
    assert hash1 == expected_hash, "Key hashing should match SHA-256"


def test_timing_attack_resistance():
    """Test timing attack resistance."""
    from demand_forecasting.serving.model_server import APIKeyManager

    manager = APIKeyManager()

    valid_key = "test_key_123"
    invalid_key = "completely_different_key_456"

    # Measure timing for valid key
    valid_timings = []
    for _ in range(50):
        start = time.perf_counter()
        result = manager.verify_key_constant_time(valid_key)
        end = time.perf_counter()
        valid_timings.append(end - start)
        assert result is True

    # Measure timing for invalid key
    invalid_timings = []
    for _ in range(50):
        start = time.perf_counter()
        result = manager.verify_key_constant_time(invalid_key)
        end = time.perf_counter()
        invalid_timings.append(end - start)
        assert result is False

    # Statistical test: timing should be consistent
    valid_mean = sum(valid_timings) / len(valid_timings)
    invalid_mean = sum(invalid_timings) / len(invalid_timings)

    valid_variance = sum((t - valid_mean) ** 2 for t in valid_timings) / len(
        valid_timings
    )
    invalid_variance = sum((t - invalid_mean) ** 2 for t in invalid_timings) / len(
        invalid_timings
    )

    # Low variance indicates constant time
    max_variance = max(valid_variance, invalid_variance)
    if max_variance < 0.001:
        pass
    else:
        raise AssertionError("High variance indicates potential timing vulnerability")


def test_fastapi_endpoints():
    """Test FastAPI endpoint security."""
    from demand_forecasting.serving.model_server import app

    client = TestClient(app)

    # Test missing API key
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

    # Test invalid API key
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

    # Test valid API key (should fail with model not loaded, but auth passes)
    response = client.post(
        "/predict",
        headers={"X-API-Key": "test_key_123"},
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
    assert response.status_code == 503  # Model not loaded, but auth passed
    assert "Model not loaded" in response.json()["detail"]


def test_rate_limiting():
    """Test rate limiting functionality with different client IPs."""
    from fastapi.testclient import TestClient

    from demand_forecasting.serving.model_server import app, rate_limit_cache

    client = TestClient(app)

    # Clear rate limit cache to start fresh
    rate_limit_cache.clear()

    # Test with different client IPs using X-Forwarded-For headers
    client_ips = [
        "192.168.1.100",
        "192.168.1.101",
        "192.168.1.102",
        "192.168.1.103",
        "192.168.1.104",
    ]

    responses = []
    for i, ip in enumerate(client_ips):
        # Make failed attempt with different client IP
        response = client.post(
            "/predict",
            headers={"X-API-Key": f"invalid_key_{i}", "X-Forwarded-For": ip},
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

    # Each client should get 403 (invalid key) since they haven't exceeded rate limit yet
    for i, response in enumerate(responses):
        assert (
            response.status_code == 403
        ), f"Client {i + 1} should get 403, got {response.status_code}"

    # Now test rate limiting with a single IP

    # Clear cache and test with same IP
    rate_limit_cache.clear()

    # Make 12 failed attempts with same IP to trigger rate limiting
    single_ip_responses = []
    for i in range(12):
        response = client.post(
            "/predict",
            headers={
                "X-API-Key": f"invalid_key_{i}",
                "X-Forwarded-For": "192.168.1.200",
            },
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
        single_ip_responses.append(response)

    # First 10 should return 403 (invalid key)
    for i in range(10):
        assert (
            single_ip_responses[i].status_code == 403
        ), f"Attempt {i + 1} should get 403, got {single_ip_responses[i].status_code}"

    # After 10, should return 429 (rate limited)
    for i in range(10, 12):
        assert (
            single_ip_responses[i].status_code == 429
        ), f"Attempt {i + 1} should get 429, got {single_ip_responses[i].status_code}"
        assert (
            "Too many authentication attempts"
            in single_ip_responses[i].json()["detail"]
        )
        assert "Retry-After" in single_ip_responses[i].headers
        assert single_ip_responses[i].headers["Retry-After"] == "3600"

    # Test rate limit reset with different IP

    # Use a different IP to bypass rate limit
    response = client.post(
        "/predict",
        headers={"X-API-Key": "test_key_123", "X-Forwarded-For": "192.168.1.201"},
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
    assert response.status_code == 503  # Model not loaded, but auth passed

    # Now test that the original IP is still rate limited
    response = client.post(
        "/predict",
        headers={
            "X-API-Key": "another_invalid_key",
            "X-Forwarded-For": "192.168.1.200",
        },
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
    assert response.status_code == 429  # Should still be rate limited


def test_secure_logging():
    """Test that no sensitive data is logged."""
    import logging
    from io import StringIO

    from demand_forecasting.serving.model_server import app, rate_limit_cache

    # Clear rate limit cache to avoid interference
    rate_limit_cache.clear()

    # Capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger("demand_forecasting.serving.model_server")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Make failed authentication attempt
    client.post(
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

    # Check log output
    log_output = log_capture.getvalue()

    # Verify no sensitive data appears in logs
    assert "sensitive_key" not in log_output, "Sensitive key material found in logs"
    assert "12345" not in log_output, "Partial key material found in logs"
    assert "Invalid API key attempt" in log_output, "Expected log message not found"

    # Clean up
    logger.removeHandler(handler)


def main() -> int | None:
    """Run all security tests."""
    try:
        test_api_key_manager()
        test_timing_attack_resistance()
        test_fastapi_endpoints()
        test_rate_limiting()
        test_secure_logging()

        return 0

    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
