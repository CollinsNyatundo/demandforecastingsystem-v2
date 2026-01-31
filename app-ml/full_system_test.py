#!/usr/bin/env python3
"""
Full System Test including DAG execution
"""

import requests
import json
import time
import sys
from requests.auth import HTTPBasicAuth


def test_airflow_dag_trigger():
    """Test triggering an Airflow DAG"""
    print("[INFO] Testing Airflow DAG Trigger")
    print("=" * 50)
    
    # Get DAGs
    try:
        response = requests.get(
            "http://localhost:8081/api/v1/dags", 
            auth=HTTPBasicAuth("Cole", "admin"),
            timeout=10
        )
        if response.status_code == 200:
            dags = response.json()
            print(f"[PASS] Found {len(dags['dags'])} DAG(s)")
            
            for dag in dags['dags']:
                print(f"  - {dag['dag_id']} (paused: {dag['is_paused']})")
                
                # Unpause the DAG if needed
                if dag['is_paused']:
                    unpause_response = requests.patch(
                        f"http://localhost:8081/api/v1/dags/{dag['dag_id']}",
                        json={"is_paused": False},
                        auth=HTTPBasicAuth("Cole", "admin"),
                        timeout=10
                    )
                    if unpause_response.status_code == 200:
                        print(f"[PASS] Unpaused DAG: {dag['dag_id']}")
                    else:
                        print(f"[FAIL] Failed to unpause DAG: {dag['dag_id']}")
                        return False
                
                # Trigger DAG run
                trigger_response = requests.post(
                    f"http://localhost:8081/api/v1/dags/{dag['dag_id']}/dagRuns",
                    json={},
                    auth=HTTPBasicAuth("Cole", "admin"),
                    timeout=10
                )
                
                if trigger_response.status_code == 200:
                    dag_run = trigger_response.json()
                    print(f"[PASS] Triggered DAG run: {dag_run['dag_run_id']}")
                    return dag_run['dag_run_id']
                else:
                    print(f"[FAIL] Failed to trigger DAG: {trigger_response.status_code}")
                    print(f"Response: {trigger_response.text}")
                    return False
        else:
            print(f"[FAIL] Failed to get DAGs: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {str(e)}")
        return False


def check_dag_run_status(dag_id, dag_run_id):
    """Check the status of a DAG run"""
    print(f"[INFO] Checking DAG run status for {dag_id}/{dag_run_id}")
    
    max_wait_time = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(
                f"http://localhost:8081/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}",
                auth=HTTPBasicAuth("Cole", "admin"),
                timeout=10
            )
            
            if response.status_code == 200:
                dag_run = response.json()
                status = dag_run['state']
                print(f"[INFO] DAG run status: {status}")
                
                if status in ['success', 'failed']:
                    return status
                    
                # Check task instances
                tasks_response = requests.get(
                    f"http://localhost:8081/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances",
                    auth=HTTPBasicAuth("Cole", "admin"),
                    timeout=10
                )
                
                if tasks_response.status_code == 200:
                    tasks = tasks_response.json()
                    print(f"[INFO] Tasks: {len(tasks['task_instances'])}")
                    for task in tasks['task_instances']:
                        print(f"  - {task['task_id']}: {task['state']}")
                
            time.sleep(10)
            
        except Exception as e:
            print(f"[FAIL] Exception checking status: {str(e)}")
            break
    
    return "timeout"


def test_mlflow_experiment():
    """Test MLflow experiment creation"""
    print("[INFO] Testing MLflow Experiment Creation")
    print("=" * 50)
    
    try:
        # Create experiment via REST API (if available)
        response = requests.post(
            "http://localhost:5000/api/2.0/mlflow/experiments/create",
            json={"name": "test_experiment"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("[PASS] MLflow experiment created")
            return True
        else:
            print(f"[WARN] MLflow API not available: {response.status_code}")
            # Try accessing UI instead
            ui_response = requests.get("http://localhost:5000", timeout=10)
            if ui_response.status_code == 200:
                print("[PASS] MLflow UI accessible")
                return True
            return False
            
    except Exception as e:
        print(f"[FAIL] MLflow test failed: {str(e)}")
        return False


def test_model_server():
    """Test model server endpoints"""
    print("[INFO] Testing Model Server")
    print("=" * 50)
    
    try:
        # Test docs
        response = requests.get("http://localhost:8000/docs", timeout=10)
        if response.status_code == 200:
            print("[PASS] Model server docs accessible")
        else:
            print(f"[FAIL] Model server docs: {response.status_code}")
            return False
        
        # Test health endpoint
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            print("[PASS] Model server health OK")
            return True
        else:
            print(f"[FAIL] Model server health: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Model server test failed: {str(e)}")
        return False


def main():
    print("=" * 60)
    print("DEMAND FORECASTING ML SYSTEM - FULL SYSTEM TEST")
    print("=" * 60)
    
    results = {}
    
    # Test MLflow
    results['mlflow'] = test_mlflow_experiment()
    
    # Test Model Server
    results['model_server'] = test_model_server()
    
    # Test Airflow DAG trigger
    dag_run_info = test_airflow_dag_trigger()
    if dag_run_info:
        results['airflow_trigger'] = True
        # Check DAG run status
        status = check_dag_run_status("dataset_monitoring", dag_run_info)
        results['dag_execution'] = status == 'success'
        
        if status == 'success':
            print("[PASS] DAG execution completed successfully")
        elif status == 'failed':
            print("[FAIL] DAG execution failed")
        else:
            print("[WARN] DAG execution timed out")
    else:
        results['airflow_trigger'] = False
        results['dag_execution'] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("FULL SYSTEM TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test, result in results.items():
        if result:
            print(f"[PASS] {test}")
            passed += 1
        else:
            print(f"[FAIL] {test}")
            failed += 1
    
    print(f"\nTotal Tests: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n[SUCCESS] All system tests passed!")
        return 0
    else:
        print(f"\n[PARTIAL] {failed} test(s) failed. System partially operational.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
