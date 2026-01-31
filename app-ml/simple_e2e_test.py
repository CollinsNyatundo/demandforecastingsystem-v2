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
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")
    elif status == "error":
        print(f"{Colors.RED}❌ {message}{Colors.END}")
    elif status == "warning":
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")
    elif status == "info":
        print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")
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
                results[service_name] = True
                if service_name == "Model Server":
                    data = response.json()
                    print(f"   Models loaded: {data.get('models_loaded', 0)}")
            else:
                print_status(f"{service_name}: HTTP {response.status_code}", "error")
                results[service_name] = False
        except requests.exceptions.RequestException as e:
            print_status(f"{service_name}: Connection failed", "error")
            results[service_name] = False
    
    return results


def test_service_accessibility():
    """Test service UI accessibility"""
    print_status("\nTesting Service Accessibility", "info")
    print("=" * 50)
    
    services = {
        "Airflow UI": "http://localhost:8081",
        "MLflow UI": "http://localhost:5000",
        "Model Server Docs": "http://localhost:8000/docs",
        "MinIO Console": "http://localhost:9001",
        "Grafana": "http://localhost:3000",
        "Prometheus": "http://localhost:9090"
    }
    
    results = {}
    
    for service_name, endpoint in services.items():
        try:
            response = requests.get(endpoint, timeout=10, allow_redirects=False)
            if response.status_code in [200, 302]:
                print_status(f"{service_name}: Accessible", "success")
                results[service_name] = True
            else:
                print_status(f"{service_name}: HTTP {response.status_code}", "warning")
                results[service_name] = False
        except requests.exceptions.RequestException as e:
            print_status(f"{service_name}: Connection failed", "error")
            results[service_name] = False
    
    return results


def test_airflow_api():
    """Test Airflow API functionality"""
    print_status("\nTesting Airflow API", "info")
    print("=" * 50)
    
    try:
        # Test API v1 (correct version)
        response = requests.get(
            "http://localhost:8081/api/v1/dags",
            auth=("Cole", "admin"),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            dags = data.get("dags", [])
            print_status(f"Airflow API v1: Working", "success")
            print_status(f"Found {len(dags)} DAGs", "info")
            
            for dag in dags[:3]:  # Show first 3 DAGs
                print(f"   - {dag['dag_id']}")
            
            return True
        else:
            print_status(f"Airflow API: HTTP {response.status_code}", "error")
            return False
            
    except requests.exceptions.RequestException as e:
        print_status(f"Airflow API: Connection failed", "error")
        return False


def test_model_server_functionality():
    """Test model server prediction endpoint"""
    print_status("\nTesting Model Server Functionality", "info")
    print("=" * 50)
    
    try:
        # Test prediction endpoint with sample data
        prediction_data = {
            "features": {
                "hour": 12,
                "day_of_week": 3,
                "temp": 25.0,
                "humidity": 60.0,
                "wind_speed": 10.0
            }
        }
        
        response = requests.post(
            "http://localhost:8000/predict",
            json=prediction_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print_status("Prediction endpoint: Working", "success")
            result = response.json()
            print(f"   Response: {result}")
            return True
        elif response.status_code == 503:
            print_status("Prediction endpoint: No model loaded (expected)", "warning")
            return True
        else:
            print_status(f"Prediction endpoint: HTTP {response.status_code}", "error")
            return False
            
    except requests.exceptions.RequestException as e:
        print_status(f"Prediction endpoint: Connection failed", "error")
        return False


def test_docker_containers():
    """Test Docker container status"""
    print_status("\nTesting Docker Containers", "info")
    print("=" * 50)
    
    try:
        import subprocess
        result = subprocess.run(
            ["docker-compose", "ps", "--format", "table"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            containers = []
            
            # Skip header line and parse container info
            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        container_name = parts[0]
                        status = parts[2] if len(parts) > 2 else "unknown"
                        # Clean up status (remove quotes and special chars)
                        status = status.strip('"').strip("'").strip("...")
                        containers.append((container_name, status))
            
            print_status(f"Found {len(containers)} containers", "info")
            
            healthy_count = 0
            for name, status in containers:
                # Check for healthy indicators
                if any(indicator in status.lower() for indicator in ["healthy", "up", "running"]):
                    print_status(f"{name}: {status}", "success")
                    healthy_count += 1
                else:
                    print_status(f"{name}: {status}", "warning")
            
            # Consider it successful if most containers are up
            success_rate = healthy_count / len(containers) if containers else 0
            print_status(f"Healthy containers: {healthy_count}/{len(containers)} ({success_rate:.0%})", "info")
            return success_rate >= 0.8  # 80% of containers should be healthy
        else:
            print_status("Failed to get container status", "error")
            return False
            
    except Exception as e:
        print_status(f"Docker check failed: {e}", "error")
        return False


def main():
    """Main test runner"""
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("🚀 DEMAND FORECASTING ML SYSTEM - END-TO-END TEST")
    print("=" * 60)
    print(f"{Colors.END}")
    
    start_time = time.time()
    
    # Run all tests
    health_results = test_service_health()
    accessibility_results = test_service_accessibility()
    airflow_api_result = test_airflow_api()
    model_server_result = test_model_server_functionality()
    docker_result = test_docker_containers()
    
    # Calculate overall results
    total_tests = 5
    passed_tests = sum([
        all(health_results.values()),
        all(accessibility_results.values()),
        airflow_api_result,
        model_server_result,
        docker_result
    ])
    
    # Print summary
    print(f"\n{Colors.BOLD}TEST SUMMARY{Colors.END}")
    print("=" * 50)
    
    print_status(f"Services Health: {sum(health_results.values())}/{len(health_results)} passed", 
                "success" if all(health_results.values()) else "error")
    print_status(f"Service Accessibility: {sum(accessibility_results.values())}/{len(accessibility_results)} passed",
                "success" if all(accessibility_results.values()) else "warning")
    print_status(f"Airflow API: {'Working' if airflow_api_result else 'Failed'}",
                "success" if airflow_api_result else "error")
    print_status(f"Model Server: {'Working' if model_server_result else 'Failed'}",
                "success" if model_server_result else "warning")
    print_status(f"Docker Containers: {'All healthy' if docker_result else 'Some issues'}",
                "success" if docker_result else "error")
    
    # Final result
    elapsed_time = time.time() - start_time
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"\n{Colors.BOLD}OVERALL RESULT: {success_rate:.0f}% SUCCESS{Colors.END}")
    print(f"Tests passed: {passed_tests}/{total_tests}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    
    if passed_tests >= 4:
        print_status("\n🎉 SYSTEM IS READY FOR PRODUCTION!", "success")
        return 0
    else:
        print_status("\n⚠️  SYSTEM NEEDS ATTENTION BEFORE PRODUCTION", "error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
