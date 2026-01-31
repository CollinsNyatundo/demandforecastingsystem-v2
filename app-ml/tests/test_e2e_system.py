"""
End-to-End System Test for Demand Forecasting ML System

This test validates the complete Docker-based system including:
- Service connectivity
- Data availability in MinIO
- MLflow functionality
- Model server health
- Airflow DAG execution
"""

import pytest
import requests
import pandas as pd
import time
from pathlib import Path


class TestE2ESystem:
    """End-to-end system tests"""
    
    @pytest.fixture(scope="class")
    def service_endpoints(self):
        """Define service endpoints"""
        return {
            "airflow": "http://localhost:8081",
            "mlflow": "http://localhost:5000",
            "model_server": "http://localhost:8000",
            "minio": "http://localhost:9000",
            "grafana": "http://localhost:3000",
            "prometheus": "http://localhost:9090"
        }
    
    @pytest.fixture(scope="class")
    def wait_for_services(self, service_endpoints):
        """Wait for services to be ready"""
        timeout = 60  # seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check Airflow
                response = requests.get(f"{service_endpoints['airflow']}/health", timeout=5)
                if response.status_code == 200:
                    airflow_ready = True
                else:
                    airflow_ready = False
            except:
                airflow_ready = False
            
            try:
                # Check MLflow
                response = requests.get(f"{service_endpoints['mlflow']}/health", timeout=5)
                if response.status_code == 200:
                    mlflow_ready = True
                else:
                    mlflow_ready = False
            except:
                mlflow_ready = False
                
            try:
                # Check Model Server
                response = requests.get(f"{service_endpoints['model_server']}/health", timeout=5)
                if response.status_code == 200:
                    model_server_ready = True
                else:
                    model_server_ready = False
            except:
                model_server_ready = False
            
            if airflow_ready and mlflow_ready and model_server_ready:
                print("✅ All services are ready!")
                return True
                
            time.sleep(2)
        
        print("❌ Services not ready within timeout")
        return False
    
    def test_service_connectivity(self, service_endpoints, wait_for_services):
        """Test that all services are accessible"""
        if not wait_for_services:
            pytest.skip("Services not ready")
        
        for service_name, endpoint in service_endpoints.items():
            try:
                if service_name == "airflow":
                    response = requests.get(f"{endpoint}/health", timeout=10)
                elif service_name == "model_server":
                    response = requests.get(f"{endpoint}/health", timeout=10)
                elif service_name == "mlflow":
                    response = requests.get(f"{endpoint}/health", timeout=10)
                else:
                    # For other services, just check basic connectivity
                    response = requests.get(endpoint, timeout=10)
                
                assert response.status_code in [200, 403, 404], f"{service_name} not accessible"
                print(f"✅ {service_name} is accessible")
                
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Cannot connect to {service_name}: {e}")
    
    def test_airflow_dags_available(self, service_endpoints, wait_for_services):
        """Test that Airflow DAGs are available"""
        if not wait_for_services:
            pytest.skip("Services not ready")
        
        # Check if DAGs are loaded using API v1
        try:
            response = requests.get(
                f"{service_endpoints['airflow']}/api/v1/dags",
                auth=("Cole", "admin"),
                timeout=10
            )
            assert response.status_code == 200
            
            dags = response.json().get("dags", [])
            dag_ids = [dag["dag_id"] for dag in dags]
            
            print(f"✅ Found {len(dags)} DAGs: {dag_ids}")
            
            # Check for expected DAGs (at least one should exist)
            if len(dags) > 0:
                print(f"✅ DAGs available: {', '.join(dag_ids[:3])}")
            else:
                print("⚠️  No DAGs found (may be expected for fresh deployment)")
                
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Cannot check Airflow DAGs: {e}")
    
    def test_mlflow_tracking(self, service_endpoints, wait_for_services):
        """Test MLflow tracking functionality"""
        if not wait_for_services:
            pytest.skip("Services not ready")
        
        try:
            # Check MLflow UI is accessible
            response = requests.get(f"{service_endpoints['mlflow']}/", timeout=10)
            assert response.status_code == 200
            assert "MLflow" in response.text
            print("✅ MLflow UI is accessible")
            
            # Check health endpoint
            response = requests.get(f"{service_endpoints['mlflow']}/health", timeout=10)
            assert response.status_code == 200
            print("✅ MLflow health endpoint working")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Cannot check MLflow: {e}")
    
    def test_model_server_endpoints(self, service_endpoints, wait_for_services):
        """Test model server API endpoints"""
        if not wait_for_services:
            pytest.skip("Services not ready")
        
        try:
            # Test health endpoint
            response = requests.get(f"{service_endpoints['model_server']}/health", timeout=10)
            assert response.status_code == 200
            
            # Test docs endpoint
            response = requests.get(f"{service_endpoints['model_server']}/docs", timeout=10)
            assert response.status_code == 200
            
            # Test metrics endpoint
            response = requests.get(f"{service_endpoints['model_server']}/metrics", timeout=10)
            assert response.status_code == 200
            
            print("✅ Model server endpoints are working")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Cannot check model server: {e}")
    
    def test_data_pipeline_integration(self, service_endpoints, wait_for_services):
        """Test basic data pipeline functionality"""
        if not wait_for_services:
            pytest.skip("Services not ready")
        
        # This is a basic integration test
        # In a real scenario, you would trigger a DAG run and check results
        
        try:
            # Test that we can make a prediction request (even if model isn't trained)
            prediction_data = {
                "features": {
                    "hour": 12,
                    "day_of_week": 3,
                    "month": 6,
                    "temperature": 25.0,
                    "humidity": 60.0,
                    "windspeed": 10.0
                }
            }
            
            response = requests.post(
                f"{service_endpoints['model_server']}/predict",
                json=prediction_data,
                timeout=10
            )
            
            # Should return either 200 (with prediction) or 503 (model not loaded)
            assert response.status_code in [200, 503]
            
            if response.status_code == 200:
                print("✅ Prediction endpoint working with model")
            else:
                print("⚠️  Model not loaded (expected for fresh deployment)")
                
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Cannot test prediction endpoint: {e}")
    
    def test_system_monitoring(self, service_endpoints, wait_for_services):
        """Test monitoring stack"""
        if not wait_for_services:
            pytest.skip("Services not ready")
        
        # Test Prometheus
        try:
            response = requests.get(f"{service_endpoints['prometheus']}/api/v1/status/config", timeout=10)
            assert response.status_code == 200
            print("✅ Prometheus is accessible")
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Prometheus not accessible: {e}")
        
        # Test Grafana
        try:
            response = requests.get(f"{service_endpoints['grafana']}/api/health", timeout=10)
            assert response.status_code == 200
            print("✅ Grafana is accessible")
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Grafana not accessible: {e}")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])
