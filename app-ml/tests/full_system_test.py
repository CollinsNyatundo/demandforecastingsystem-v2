#!/usr/bin/env python3
"""Full System Test including DAG execution."""

import sys
import time

import requests
from requests.auth import HTTPBasicAuth


def test_airflow_dag_trigger():
    """Test triggering an Airflow DAG."""
    # Get DAGs
    try:
        response = requests.get(
            "http://localhost:8081/api/v1/dags",
            auth=HTTPBasicAuth("Cole", "admin"),
            timeout=10,
        )
        if response.status_code == 200:
            dags = response.json()

            for dag in dags["dags"]:
                # Unpause the DAG if needed
                if dag["is_paused"]:
                    unpause_response = requests.patch(
                        f"http://localhost:8081/api/v1/dags/{dag['dag_id']}",
                        json={"is_paused": False},
                        auth=HTTPBasicAuth("Cole", "admin"),
                        timeout=10,
                    )
                    if unpause_response.status_code == 200:
                        pass
                    else:
                        return False

                # Trigger DAG run
                trigger_response = requests.post(
                    f"http://localhost:8081/api/v1/dags/{dag['dag_id']}/dagRuns",
                    json={},
                    auth=HTTPBasicAuth("Cole", "admin"),
                    timeout=10,
                )

                if trigger_response.status_code == 200:
                    dag_run = trigger_response.json()
                    return dag_run["dag_run_id"]
                return False
        else:
            return False

    except Exception:
        return False


def check_dag_run_status(dag_id, dag_run_id):
    """Check the status of a DAG run."""
    max_wait_time = 300  # 5 minutes
    start_time = time.time()

    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(
                f"http://localhost:8081/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}",
                auth=HTTPBasicAuth("Cole", "admin"),
                timeout=10,
            )

            if response.status_code == 200:
                dag_run = response.json()
                status = dag_run["state"]

                if status in ["success", "failed"]:
                    return status

                # Check task instances
                tasks_response = requests.get(
                    f"http://localhost:8081/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances",
                    auth=HTTPBasicAuth("Cole", "admin"),
                    timeout=10,
                )

                if tasks_response.status_code == 200:
                    tasks = tasks_response.json()
                    for _task in tasks["task_instances"]:
                        pass

            time.sleep(10)

        except Exception:
            break

    return "timeout"


def test_mlflow_experiment() -> bool | None:
    """Test MLflow experiment creation."""
    try:
        # Create experiment via REST API (if available)
        response = requests.post(
            "http://localhost:5000/api/2.0/mlflow/experiments/create",
            json={"name": "test_experiment"},
            timeout=10,
        )

        if response.status_code == 200:
            return True
        # Try accessing UI instead
        ui_response = requests.get("http://localhost:5000", timeout=10)
        return ui_response.status_code == 200

    except Exception:
        return False


def test_model_server() -> bool | None:
    """Test model server endpoints."""
    try:
        # Test docs
        response = requests.get("http://localhost:8000/docs", timeout=10)
        if response.status_code == 200:
            pass
        else:
            return False

        # Test health endpoint
        response = requests.get("http://localhost:8000/health", timeout=10)
        return response.status_code == 200

    except Exception:
        return False


def main() -> int:
    results = {}

    # Test MLflow
    results["mlflow"] = test_mlflow_experiment()

    # Test Model Server
    results["model_server"] = test_model_server()

    # Test Airflow DAG trigger
    dag_run_info = test_airflow_dag_trigger()
    if dag_run_info:
        results["airflow_trigger"] = True
        # Check DAG run status
        status = check_dag_run_status("dataset_monitoring", dag_run_info)
        results["dag_execution"] = status == "success"

        if status in {"success", "failed"}:
            pass
        else:
            pass
    else:
        results["airflow_trigger"] = False
        results["dag_execution"] = False

    # Summary

    passed = 0
    failed = 0

    for _test, result in results.items():
        if result:
            passed += 1
        else:
            failed += 1

    if failed == 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
