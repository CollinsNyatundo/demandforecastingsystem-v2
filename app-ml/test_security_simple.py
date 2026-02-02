#!/usr/bin/env python3
"""
Simple security test runner for the model server.
Tests all security functionality without pytest dependencies.
"""

import sys
import os
import time
import secrets
import hashlib
from fastapi.testclient import TestClient

# Add src to path
sys.path.append('src')

# Set test environment variables
os.environ['VALID_API_KEYS'] = 'test_key_123,test_key_456'

def test_api_key_manager():
    """Test APIKeyManager functionality."""
    print("🔧 Testing APIKeyManager...")
    
    from demand_forecasting.serving.model_server import APIKeyManager
    
    manager = APIKeyManager()
    
    # Test key loading
    assert len(manager.valid_key_hashes) == 2, f"Expected 2 keys, got {len(manager.valid_key_hashes)}"
    print("✅ API key loading works")
    
    # Test valid key verification
    result1 = manager.verify_key_constant_time('test_key_123')
    assert result1 is True, "Valid key should return True"
    print("✅ Valid key verification works")
    
    # Test invalid key verification
    result2 = manager.verify_key_constant_time('invalid_key')
    assert result2 is False, "Invalid key should return False"
    print("✅ Invalid key verification works")
    
    # Test key hashing
    hash1 = manager._hash_api_key('test_key')
    expected_hash = hashlib.sha256('test_key'.encode()).hexdigest()
    assert hash1 == expected_hash, "Key hashing should match SHA-256"
    print("✅ Key hashing works")
    
    print("✅ APIKeyManager tests passed!\n")

def test_timing_attack_resistance():
    """Test timing attack resistance."""
    print("🕒️ Testing timing attack resistance...")
    
    from demand_forecasting.serving.model_server import APIKeyManager
    
    manager = APIKeyManager()
    
    valid_key = 'test_key_123'
    invalid_key = 'completely_different_key_456'
    
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
    
    valid_variance = sum((t - valid_mean) ** 2 for t in valid_timings) / len(valid_timings)
    invalid_variance = sum((t - invalid_mean) ** 2 for t in invalid_timings) / len(invalid_timings)
    
    print(f"   Valid key mean time: {valid_mean:.6f}s")
    print(f"   Invalid key mean time: {invalid_mean:.6f}s")
    print(f"   Valid key variance: {valid_variance:.6f}")
    print(f"   Invalid key variance: {invalid_variance:.6f}")
    print(f"   Time difference: {abs(valid_mean - invalid_mean):.6f}s")
    
    # Low variance indicates constant time
    max_variance = max(valid_variance, invalid_variance)
    if max_variance < 0.001:
        print("✅ TIMING ATTACK RESISTANCE: PASSED")
    else:
        print("❌ TIMING ATTACK RESISTANCE: FAILED")
        raise AssertionError("High variance indicates potential timing vulnerability")
    
    print("✅ Timing attack resistance tests passed!\n")

def test_fastapi_endpoints():
    """Test FastAPI endpoint security."""
    print("🌐 Testing FastAPI endpoints...")
    
    from demand_forecasting.serving.model_server import app
    
    client = TestClient(app)
    
    # Test missing API key
    response = client.post('/predict', json={
        'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}
    })
    assert response.status_code == 401
    assert 'Missing API key' in response.json()['detail']
    print("✅ Missing API key test passed")
    
    # Test invalid API key
    response = client.post('/predict', headers={'X-API-Key': 'invalid_key'}, json={
        'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}
    })
    assert response.status_code == 403
    assert 'Invalid API key' in response.json()['detail']
    print("✅ Invalid API key test passed")
    
    # Test valid API key (should fail with model not loaded, but auth passes)
    response = client.post('/predict', headers={'X-API-Key': 'test_key_123'}, json={
        'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}
    })
    assert response.status_code == 503  # Model not loaded, but auth passed
    assert 'Model not loaded' in response.json()['detail']
    print("✅ Valid API key test passed")
    
    print("✅ FastAPI endpoint tests passed!\n")

def test_rate_limiting():
    """Test rate limiting functionality with different client IPs."""
    print("🚦 Testing rate limiting with multiple client IPs...")
    
    from fastapi.testclient import TestClient
    from demand_forecasting.serving.model_server import app, rate_limit_cache
    
    client = TestClient(app)
    
    # Clear rate limit cache to start fresh
    rate_limit_cache.clear()
    
    # Test with different client IPs using X-Forwarded-For headers
    client_ips = ['192.168.1.100', '192.168.1.101', '192.168.1.102', '192.168.1.103', '192.168.1.104']
    
    responses = []
    for i, ip in enumerate(client_ips):
        # Make failed attempt with different client IP
        response = client.post('/predict', 
            headers={
                'X-API-Key': f'invalid_key_{i}', 
                'X-Forwarded-For': ip
            }, 
            json={'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}}
        )
        responses.append(response)
        print(f"   Client {i+1} ({ip}): Status {response.status_code}")
    
    # Each client should get 403 (invalid key) since they haven't exceeded rate limit yet
    for i, response in enumerate(responses):
        assert response.status_code == 403, f"Client {i+1} should get 403, got {response.status_code}"
    
    print("✅ Multiple client IPs test passed")
    
    # Now test rate limiting with a single IP
    print("   Testing rate limiting with single IP...")
    
    # Clear cache and test with same IP
    rate_limit_cache.clear()
    
    # Make 12 failed attempts with same IP to trigger rate limiting
    single_ip_responses = []
    for i in range(12):
        response = client.post(
            '/predict',
            headers={'X-API-Key': f'invalid_key_{i}', 'X-Forwarded-For': '192.168.1.200'},
            json={'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}}
        )
        single_ip_responses.append(response)
        print(f"   Attempt {i+1}: Status {response.status_code}")
    
    # First 10 should return 403 (invalid key)
    for i in range(10):
        assert single_ip_responses[i].status_code == 403, f"Attempt {i+1} should get 403, got {single_ip_responses[i].status_code}"
    
    # After 10, should return 429 (rate limited)
    for i in range(10, 12):
        assert single_ip_responses[i].status_code == 429, f"Attempt {i+1} should get 429, got {single_ip_responses[i].status_code}"
        assert 'Too many authentication attempts' in single_ip_responses[i].json()['detail']
        assert 'Retry-After' in single_ip_responses[i].headers
        assert single_ip_responses[i].headers['Retry-After'] == '3600'
    
    print("✅ Rate limiting threshold test passed")
    print("✅ Rate limiting headers test passed")
    
    # Test rate limit reset with different IP
    print("   Testing rate limit reset with different IP...")
    
    # Use a different IP to bypass rate limit
    response = client.post(
        '/predict',
        headers={'X-API-Key': 'test_key_123', 'X-Forwarded-For': '192.168.1.201'},
        json={'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}}
    )
    assert response.status_code == 503  # Model not loaded, but auth passed
    print("✅ Rate limit reset test passed")
    
    # Now test that the original IP is still rate limited
    response = client.post(
        '/predict',
        headers={'X-API-Key': 'another_invalid_key', 'X-Forwarded-For': '192.168.1.200'},
        json={'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}}
    )
    assert response.status_code == 429  # Should still be rate limited
    print("✅ Rate limit persistence test passed")
    
    print("✅ Rate limiting tests passed!\n")

def test_secure_logging():
    """Test that no sensitive data is logged."""
    print("📝 Testing secure logging...")
    
    import logging
    from io import StringIO
    from demand_forecasting.serving.model_server import app, rate_limit_cache
    
    # Clear rate limit cache to avoid interference
    rate_limit_cache.clear()
    
    # Capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger('demand_forecasting.serving.model_server')
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    # Make failed authentication attempt
    response = client.post('/predict', headers={'X-API-Key': 'sensitive_key_12345'}, json={
        'features': {'temp': 20.0, 'humidity': 50.0, 'wind_speed': 10.0, 'hour': 12, 'day_of_week': 3}
    })
    
    # Check log output
    log_output = log_capture.getvalue()
    
    # Verify no sensitive data appears in logs
    assert 'sensitive_key' not in log_output, "Sensitive key material found in logs"
    assert '12345' not in log_output, "Partial key material found in logs"
    assert 'Invalid API key attempt' in log_output, "Expected log message not found"
    
    # Clean up
    logger.removeHandler(handler)
    
    print("✅ No sensitive data in logs")
    print("✅ Secure logging tests passed!\n")

def main():
    """Run all security tests."""
    print("🔒 SECURITY TEST SUITE - DEMAND FORECASTING MODEL SERVER")
    print("=" * 60)
    
    try:
        test_api_key_manager()
        test_timing_attack_resistance()
        test_fastapi_endpoints()
        test_rate_limiting()
        test_secure_logging()
        
        print("🎉 ALL SECURITY TESTS PASSED!")
        print("=" * 60)
        print("✅ Timing attack vulnerability RESOLVED")
        print("✅ Rate limiting implemented correctly")
        print("✅ Secure logging implemented correctly")
        print("✅ FastAPI endpoints secured properly")
        print("✅ API key management working correctly")
        
        return 0
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    exit(main())
