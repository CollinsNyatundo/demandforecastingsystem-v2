"""API Client module for connecting the dashboard to live backend services.

Provides async-safe functions to check service health and fetch metrics
from the MLOps backend (model-server, MLflow, Airflow, MinIO).
Falls back gracefully to demo data when services are unavailable.
"""

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Service URLs (Docker internal network or localhost fallback)
MODEL_SERVER_URL = os.environ.get("MODEL_SERVER_URL", "http://localhost:8000")
MLFLOW_URL = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
AIRFLOW_URL = os.environ.get("AIRFLOW_URL", "http://localhost:8081")
MINIO_URL = os.environ.get("MINIO_URL", "http://localhost:9000")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000")

# Timeout for all service checks (seconds)
SERVICE_TIMEOUT = float(os.environ.get("SERVICE_CHECK_TIMEOUT", "3"))


def _safe_get(url: str, timeout: float = SERVICE_TIMEOUT, **kwargs) -> dict | None:
    """Make a safe GET request with timeout, returning None on failure."""
    try:
        resp = requests.get(url, timeout=timeout, **kwargs)
        if resp.status_code < 400:
            return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"status": "ok", "code": resp.status_code}
        return None
    except Exception as e:
        logger.debug(f"Service check failed for {url}: {e}")
        return None


def check_model_server() -> dict:
    """Check model server health and get model info."""
    health = _safe_get(f"{MODEL_SERVER_URL}/health")
    model_info = _safe_get(f"{MODEL_SERVER_URL}/model/info")
    return {
        "name": "Model Server",
        "icon": "bi-cpu",
        "color": "text-info",
        "healthy": health is not None,
        "status": "Healthy" if health else "Unreachable",
        "detail": f"Models: {health.get('models_loaded', '?')}" if health else "Service unavailable",
        "model_info": model_info,
    }


def check_mlflow() -> dict:
    """Check MLflow tracking server health."""
    # MLflow health check varies by version
    result = _safe_get(f"{MLFLOW_URL}/health") or _safe_get(f"{MLFLOW_URL}/api/2.0/mlflow/experiments/search?max_results=1")
    return {
        "name": "MLflow Tracking",
        "icon": "bi-graph-up",
        "color": "text-warning",
        "healthy": result is not None,
        "status": "Operational" if result else "Unreachable",
        "detail": "Tracking active" if result else "Service unavailable",
    }


def check_airflow() -> dict:
    """Check Airflow webserver health."""
    result = _safe_get(f"{AIRFLOW_URL}/health")
    scheduler_ok = False
    if result and isinstance(result, dict):
        scheduler_status = result.get("scheduler", {}).get("status", "unknown")
        scheduler_ok = scheduler_status == "healthy"
    return {
        "name": "Airflow Pipeline",
        "icon": "bi-hdd-network",
        "color": "text-info",
        "healthy": scheduler_ok,
        "status": "Healthy" if scheduler_ok else ("Degraded" if result else "Unreachable"),
        "detail": f"Scheduler: {result.get('scheduler', {}).get('status', 'unknown')}" if result else "Service unavailable",
    }


def check_minio() -> dict:
    """Check MinIO storage health."""
    result = _safe_get(f"{MINIO_URL}/minio/health/live")
    return {
        "name": "MinIO Storage",
        "icon": "bi-box-seam",
        "color": "text-danger",
        "healthy": result is not None,
        "status": "Online" if result else "Unreachable",
        "detail": "Storage available" if result else "Service unavailable",
    }


def check_grafana() -> dict:
    """Check Grafana health."""
    result = _safe_get(f"{GRAFANA_URL}/api/health")
    return {
        "name": "Grafana",
        "icon": "bi-bar-chart-line",
        "color": "text-success",
        "healthy": result is not None,
        "status": "Online" if result else "Unreachable",
        "detail": "Dashboards available" if result else "Service unavailable",
    }


def get_all_service_health() -> list[dict]:
    """Check health of all backend services."""
    return [
        check_model_server(),
        check_mlflow(),
        check_airflow(),
        check_minio(),
        check_grafana(),
    ]


def get_drift_metrics() -> dict:
    """Fetch drift metrics from model server endpoint."""
    result = _safe_get(f"{MODEL_SERVER_URL}/metrics/drift")
    if result and result.get("status") == "ok":
        return result.get("metrics", {})
    return {}


def get_latest_mlflow_run() -> dict | None:
    """Fetch the latest MLflow run metrics for the demand_forecasting experiment."""
    try:
        # Search for the experiment
        exp_result = _safe_get(
            f"{MLFLOW_URL}/api/2.0/mlflow/experiments/get-by-name",
            params={"experiment_name": "demand_forecasting"},
        )
        if not exp_result:
            return None

        experiment_id = exp_result.get("experiment", {}).get("experiment_id")
        if not experiment_id:
            return None

        # Get latest completed run
        resp = requests.post(
            f"{MLFLOW_URL}/api/2.0/mlflow/runs/search",
            json={
                "experiment_ids": [experiment_id],
                "max_results": 1,
                "order_by": ["start_time DESC"],
                "filter_string": "status = 'FINISHED'",
            },
            timeout=SERVICE_TIMEOUT,
        )
        if resp.status_code != 200:
            return None

        runs = resp.json().get("runs", [])
        if not runs:
            return None

        run = runs[0]
        metrics = run.get("data", {}).get("metrics", {})
        tags = run.get("data", {}).get("tags", {})
        return {
            "run_id": run.get("info", {}).get("run_id"),
            "status": run.get("info", {}).get("status"),
            "start_time": run.get("info", {}).get("start_time"),
            "rmse": metrics.get("rmse"),
            "mae": metrics.get("mae"),
            "mape": metrics.get("mape"),
            "model_version": tags.get("model_version"),
            "pipeline_version": tags.get("pipeline_version"),
            "environment": tags.get("environment"),
        }
    except Exception as e:
        logger.debug(f"Failed to fetch MLflow run: {e}")
        return None


def send_test_prediction(features: dict | None = None) -> dict | None:
    """Send a test prediction request to the model server."""
    if features is None:
        features = {
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3,
            "month": 6,
        }

    api_key = os.environ.get("API_KEY", os.environ.get("MODEL_SERVER_API_KEY", ""))

    try:
        resp = requests.post(
            f"{MODEL_SERVER_URL}/predict",
            json={"features": features},
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=SERVICE_TIMEOUT * 2,
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"Status {resp.status_code}", "detail": resp.text}
    except Exception as e:
        return {"error": str(e)}
