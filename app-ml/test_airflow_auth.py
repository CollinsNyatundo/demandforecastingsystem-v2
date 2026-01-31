#!/usr/bin/env python
import requests

# Test without auth
print("Testing without auth:")
r = requests.get("http://localhost:8081/api/v1/dags", timeout=5)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:200]}\n")

# Test with basic auth
print("Testing with basic auth (admin/admin):")
r = requests.get(
    "http://localhost:8081/api/v1/dags", auth=("admin", "admin"), timeout=5
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:200]}\n")

# Check Airflow version
print("Testing Airflow health endpoint:")
r = requests.get("http://localhost:8081/health", timeout=5)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")
