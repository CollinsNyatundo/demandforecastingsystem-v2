#!/usr/bin/env python
import requests

# Test without auth
r = requests.get("http://localhost:8081/api/v1/dags", timeout=5)

# Test with basic auth
r = requests.get(
    "http://localhost:8081/api/v1/dags", auth=("admin", "admin"), timeout=5
)

# Check Airflow version
r = requests.get("http://localhost:8081/health", timeout=5)
