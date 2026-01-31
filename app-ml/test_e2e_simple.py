#!/usr/bin/env python3
"""
Simple End-to-End System Test Runner
Tests all Docker services without requiring pytest
"""

import requests
import json
import time
import sys


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_status(message, status="info"):
    if status == "success":
        print(f"[PASS] {message}")
    elif status == "error":
        print(f"[FAIL] {message}")
    elif status == "warning":
        print(f"[WARN] {message}")
    elif status == "info":
        print(f"[INFO] {message}")
    else:
        print(message)


def test_service_health():
    """Test all service health endpoints"""
    print_status("Testing Service Health", "info")
    print("=" * 50)
    
    services = {
        "Airflow": "http://localhost:8081/health",
        "MLflow": "http://localhost:5000/health", 
        "Model Server": "http://localhost:8000/health"
    }
    
    results = {}
    
    for service_name, endpoint in services.items():
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                print_status(f"{service_name}: Healthy", "success")
                results[service_name] = "HEALTHY"
            else:
                print_status(f"{service_name}: HTTP {response.status_code}", "error")
                results[service_name] = f"HTTP_{response.status_code}"
        except requests.exceptions.RequestException as e:
            print_status(f"{service_name}: Connection failed - {str(e)}", "error")
            results[service_name] = "FAILED"
    
    return results


def test_service_functionality():
    """Test basic functionality of services"""
    print_status("\nTesting Service Functionality", "info")
    print("=" * 50)
    
    results = {}
    
    # Test MLflow
    try:
        response = requests.get("http://localhost:5000/api/2.0/mlflow/experiments/list", timeout=10)
        if response.status_code == 200:
            print_status("MLflow API: Working", "success")
            results["MLflow_API"] = "WORKING"
        else:
            print_status(f"MLflow API: HTTP {response.status_code}", "error")
            results["MLflow_API"] = f"HTTP_{response.status_code}"
    except Exception as e:
        print_status(f"MLflow API: Failed - {str(e)}", "error")
        results["MLflow_API"] = "FAILED"
    
    # Test Model Server
    try:
        response = requests.get("http://localhost:8000/docs", timeout=10)
        if response.status_code == 200:
            print_status("Model Server Docs: Working", "success")
            results["Model_Server_Docs"] = "WORKING"
        else:
            print_status(f"Model Server Docs: HTTP {response.status_code}", "error")
            results["Model_Server_Docs"] = f"HTTP_{response.status_code}"
    except Exception as e:
        print_status(f"Model Server Docs: Failed - {str(e)}", "error")
        results["Model_Server_Docs"] = "FAILED"
    
    # Test Airflow
    try:
        response = requests.get("http://localhost:8081/api/v1/dags", timeout=10)
        if response.status_code == 200:
            print_status("Airflow API: Working", "success")
            results["Airflow_API"] = "WORKING"
        else:
            print_status(f"Airflow API: HTTP {response.status_code}", "error")
            results["Airflow_API"] = f"HTTP_{response.status_code}"
    except Exception as e:
        print_status(f"Airflow API: Failed - {str(e)}", "error")
        results["Airflow_API"] = "FAILED"
    
    return results


def test_minio_connectivity():
    """Test MinIO connectivity"""
    print_status("\nTesting MinIO Connectivity", "info")
    print("=" * 50)
    
    try:
        response = requests.get("http://localhost:9000/minio/health/live", timeout=10)
        if response.status_code == 200:
            print_status("MinIO: Healthy", "success")
            return "HEALTHY"
        else:
            print_status(f"MinIO: HTTP {response.status_code}", "error")
            return f"HTTP_{response.status_code}"
    except Exception as e:
        print_status(f"MinIO: Failed - {str(e)}", "error")
        return "FAILED"


def main():
    print("=" * 60)
    print("DEMAND FORECASTING ML SYSTEM - END-TO-END TEST")
    print("=" * 60)
    
    all_results = {}
    
    # Test service health
    health_results = test_service_health()
    all_results.update(health_results)
    
    # Test service functionality
    func_results = test_service_functionality()
    all_results.update(func_results)
    
    # Test MinIO
    minio_result = test_minio_connectivity()
    all_results["MinIO"] = minio_result
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for service, status in all_results.items():
        if status in ["HEALTHY", "WORKING"]:
            print_status(f"{service}: {status}", "success")
            passed += 1
        else:
            print_status(f"{service}: {status}", "error")
            failed += 1
    
    print(f"\nTotal Tests: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print_status("\nAll tests passed! System is fully operational.", "success")
        return 0
    else:
        print_status(f"\n{failed} tests failed. Check logs for details.", "error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
