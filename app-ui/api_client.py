"""API Client — connects the dashboard to live backend services.

Falls back gracefully to demo data when services are unavailable.
All functions are synchronous (Flask/Dash thread model).
"""

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# ── Service URLs (Docker internal network or localhost fallback) ───────────────
MODEL_SERVER_URL = os.environ.get("MODEL_SERVER_URL", "http://localhost:8000")
MLFLOW_URL       = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
AIRFLOW_URL      = os.environ.get("AIRFLOW_URL", "http://localhost:8081")
MINIO_URL        = os.environ.get("MINIO_URL", "http://localhost:9000")
GRAFANA_URL      = os.environ.get("GRAFANA_URL", "http://localhost:3000")

POSTGRES_HOST    = os.environ.get("POSTGRES_HOST", "postgres")
POSTGRES_PORT    = int(os.environ.get("POSTGRES_PORT", "5432"))
REDIS_HOST       = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT       = int(os.environ.get("REDIS_PORT", "6379"))
PROMETHEUS_URL   = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
NGINX_URL        = os.environ.get("NGINX_URL", "http://nginx:8080")
OPTUNA_URL       = os.environ.get("OPTUNA_URL", "http://optuna-dashboard:8080")
CLEARML_API_URL  = os.environ.get("CLEARML_API_URL", "http://clearml-apiserver:8008")

# API key for the model server's /predict endpoint
MODEL_API_KEY    = os.environ.get("API_KEY", os.environ.get("MODEL_SERVER_API_KEY", ""))

# Timeout for health checks (seconds)
SERVICE_TIMEOUT  = float(os.environ.get("SERVICE_CHECK_TIMEOUT", "3"))

# MLflow experiment name
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT_NAME", "demand_forecasting")


# ── Low-level helpers ─────────────────────────────────────────────────────────

import socket

def _safe_socket(host: str, port: int, timeout: float = SERVICE_TIMEOUT) -> bool:
    """Socket connect with timeout; returns True on success, False on failure."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception as e:
        logger.debug(f"SOCKET connect to {host}:{port} failed: {e}")
        return False

def _safe_get(url: str, timeout: float = SERVICE_TIMEOUT, **kwargs) -> dict | None:
    """GET with timeout; returns None on any failure."""
    try:
        resp = requests.get(url, timeout=timeout, **kwargs)
        if resp.status_code < 400:
            ct = resp.headers.get("content-type", "")
            return resp.json() if "json" in ct else {"status": "ok", "code": resp.status_code}
        return None
    except Exception as e:
        logger.debug(f"GET {url} failed: {e}")
        return None


def _safe_post(url: str, payload: dict, timeout: float = SERVICE_TIMEOUT, **kwargs) -> dict | None:
    """POST JSON with timeout; returns None on any failure."""
    try:
        resp = requests.post(url, json=payload, timeout=timeout, **kwargs)
        if resp.status_code < 400:
            return resp.json()
        logger.debug(f"POST {url} returned {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.debug(f"POST {url} failed: {e}")
        return None


def _mlflow_experiment_id() -> str | None:
    """Resolve MLflow experiment name → experiment_id."""
    try:
        result = _safe_get(
            f"{MLFLOW_URL}/api/2.0/mlflow/experiments/get-by-name",
            params={"experiment_name": MLFLOW_EXPERIMENT},
        )
        if result:
            return result.get("experiment", {}).get("experiment_id")
    except Exception:
        pass
    return None


# ── Service Health ────────────────────────────────────────────────────────────

def check_model_server() -> dict:
    health = _safe_get(f"{MODEL_SERVER_URL}/health")
    info   = _safe_get(f"{MODEL_SERVER_URL}/model/info")
    model_type = "—"
    if info:
        model_type = info.get("model_type", info.get("model_id", "CatBoost"))
    return {
        "name": "Model Server",
        "icon": "bi-cpu",
        "color": "text-info",
        "healthy": health is not None,
        "status": "Healthy" if health else "Unreachable",
        "detail": f"Model: {model_type} · {health.get('models_loaded', 0)} loaded" if health else "Service unavailable",
    }


def check_mlflow() -> dict:
    result = _safe_get(f"{MLFLOW_URL}/health") or _safe_get(
        f"{MLFLOW_URL}/api/2.0/mlflow/experiments/search?max_results=1"
    )
    return {
        "name": "MLflow Tracking",
        "icon": "bi-graph-up",
        "color": "text-warning",
        "healthy": result is not None,
        "status": "Operational" if result else "Unreachable",
        "detail": "Tracking active" if result else "Service unavailable",
    }


def check_airflow() -> dict:
    result = _safe_get(f"{AIRFLOW_URL}/health")
    scheduler_ok = False
    if result and isinstance(result, dict):
        scheduler_ok = result.get("scheduler", {}).get("status") == "healthy"
    return {
        "name": "Airflow Pipeline",
        "icon": "bi-hdd-network",
        "color": "text-info",
        "healthy": scheduler_ok,
        "status": "Healthy" if scheduler_ok else ("Degraded" if result else "Unreachable"),
        "detail": f"Scheduler: {result.get('scheduler', {}).get('status', 'unknown')}" if result else "Service unavailable",
    }

def trigger_airflow_dag(dag_id: str) -> dict:
    """Trigger an Airflow DAG run via REST API."""
    import requests
    # Default airflow credentials in dev setup
    AIRFLOW_USER = os.environ.get("AIRFLOW_WWW_USER_USERNAME", "admin")
    AIRFLOW_PASS = os.environ.get("AIRFLOW_WWW_USER_PASSWORD", "admin")
    try:
        resp = requests.post(
            f"{AIRFLOW_URL}/api/v1/dags/{dag_id}/dagRuns",
            timeout=SERVICE_TIMEOUT * 2,
            auth=(AIRFLOW_USER, AIRFLOW_PASS),
            json={"conf": {}}
        )
        if resp.status_code in (200, 201):
            return {"success": True, "message": f"Successfully triggered {dag_id}"}
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_minio() -> dict:
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
    result = _safe_get(f"{GRAFANA_URL}/api/health")
    return {
        "name": "Grafana",
        "icon": "bi-bar-chart-line",
        "color": "text-success",
        "healthy": result is not None,
        "status": "Online" if result else "Unreachable",
        "detail": "Dashboards available" if result else "Service unavailable",
    }


def check_postgres() -> dict:
    is_up = _safe_socket(POSTGRES_HOST, POSTGRES_PORT)
    return {
        "name": "PostgreSQL",
        "icon": "bi-database",
        "color": "text-primary",
        "healthy": is_up,
        "status": "Online" if is_up else "Unreachable",
        "detail": "Database responding" if is_up else "Service unavailable",
    }


def check_redis() -> dict:
    is_up = _safe_socket(REDIS_HOST, REDIS_PORT)
    return {
        "name": "Redis Cache",
        "icon": "bi-lightning-charge",
        "color": "text-danger",
        "healthy": is_up,
        "status": "Online" if is_up else "Unreachable",
        "detail": "Cache responding" if is_up else "Service unavailable",
    }


def check_prometheus() -> dict:
    result = _safe_get(f"{PROMETHEUS_URL}/-/healthy")
    return {
        "name": "Prometheus",
        "icon": "bi-activity",
        "color": "text-warning",
        "healthy": result is not None,
        "status": "Online" if result else "Unreachable",
        "detail": "Monitoring active" if result else "Service unavailable",
    }


def check_nginx() -> dict:
    result = _safe_get(f"{NGINX_URL}/nginx_status")
    return {
        "name": "Nginx Load Balancer",
        "icon": "bi-diagram-2",
        "color": "text-success",
        "healthy": result is not None,
        "status": "Online" if result else "Unreachable",
        "detail": "Gateway active" if result else "Service unavailable",
    }


def check_optuna() -> dict:
    result = _safe_get(f"{OPTUNA_URL}/", timeout=1.0)
    return {
        "name": "Optuna Dashboard",
        "icon": "bi-speedometer2",
        "color": "text-info",
        "healthy": result is not None,
        "status": "Online" if result else "Unreachable",
        "detail": "HPO UI available" if result else "Service unavailable",
    }


def check_clearml() -> dict:
    """Check ClearML API server health."""
    return {
        "name": "ClearML",
        "icon": "bi-cpu",
        "color": "text-primary" if _safe_get(f"{CLEARML_API_URL}/debug.ping", timeout=2) else "text-danger",
        "healthy": bool(_safe_get(f"{CLEARML_API_URL}/debug.ping", timeout=2)),
        "status": "Online" if _safe_get(f"{CLEARML_API_URL}/debug.ping", timeout=2) else "Offline",
        "detail": "Experiment tracking",
    }


def get_prometheus_metrics() -> dict:
    """Fetch live usage metrics from Prometheus."""
    metrics = {"total_predictions": 0, "avg_latency_ms": 0, "active_sessions": 0}
    try:
        # Total requests
        resp = _safe_get(f"{PROMETHEUS_URL}/api/v1/query?query=sum(prediction_requests_total)")
        if resp and resp.get("status") == "success" and resp["data"]["result"]:
            metrics["total_predictions"] = int(float(resp["data"]["result"][0]["value"][1]))
        
        # Latency
        resp_lat = _safe_get(f"{PROMETHEUS_URL}/api/v1/query?query=sum(rate(prediction_duration_seconds_sum[5m]))/sum(rate(prediction_duration_seconds_count[5m]))")
        if resp_lat and resp_lat.get("status") == "success" and resp_lat["data"]["result"]:
            val = float(resp_lat["data"]["result"][0]["value"][1])
            if not math.isnan(val):
                metrics["avg_latency_ms"] = int(val * 1000)
    except Exception as e:
        import logging
        logging.warning("Failed to fetch Prometheus metrics: %s", e)
    return metrics


def get_all_service_health() -> list[dict]:
    """Check health of all backend services in sequence."""
    return [
        check_model_server(),
        check_nginx(),
        check_airflow(),
        check_mlflow(),
        check_postgres(),
        check_redis(),
        check_minio(),
        check_clearml(),
        check_optuna(),
        check_grafana(),
        check_prometheus(),
    ]


# ── Drift Metrics ─────────────────────────────────────────────────────────────

def get_drift_metrics() -> dict:
    """Fetch Evidently drift metrics from model server.

    Returns a flat dict like:
      {evidently_dataset_drift: 0, evidently_drift_share: 0.5, ...}
    """
    result = _safe_get(f"{MODEL_SERVER_URL}/metrics/drift", timeout=SERVICE_TIMEOUT * 1.5)
    if not result:
        return {}
    # The endpoint can return either {metrics: {...}} or the flat dict directly
    if "metrics" in result and isinstance(result["metrics"], dict):
        return result["metrics"]
    # Also handle Prometheus-text responses parsed as non-json
    return {k: v for k, v in result.items() if k not in ("status", "code")}

def get_latest_drift_report_name() -> str | None:
    """Find the most recent Evidently HTML report in 09_reports."""
    import glob
    from pathlib import Path
    
    # Resolve the project root dynamically, similarly to config_theme.py
    project_root = Path(os.environ.get("PROJECT_ROOT", str(Path(__file__).resolve().parents[1])))
    reports_dir = project_root / "app-ml" / "data" / "09_reports"
    
    files = glob.glob(str(reports_dir / "*.html"))
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return os.path.basename(files[0])


# ── MLflow Run Queries ────────────────────────────────────────────────────────

def _parse_run(run: dict) -> dict:
    """Normalize a raw MLflow run dict into our internal schema."""
    info    = run.get("info", {})
    data    = run.get("data", {})
    metrics = {m["key"]: m["value"] for m in data.get("metrics", [])} if isinstance(data.get("metrics"), list) else data.get("metrics", {})
    params  = {p["key"]: p["value"] for p in data.get("params", [])}  if isinstance(data.get("params"),  list) else data.get("params",  {})
    tags    = {t["key"]: t["value"] for t in data.get("tags", [])}    if isinstance(data.get("tags"),    list) else data.get("tags",    {})

    # Detect model type from tags or registered model name
    model_type = (
        tags.get("model_type")
        or tags.get("mlflow.runName", "")
        or "CatBoost"
    )
    if "ensemble" in model_type.lower():
        model_type = "Stacking Ensemble"
    elif "catboost" in model_type.lower() or not model_type:
        model_type = "CatBoost"

    ts = info.get("start_time")
    start_time_str = "—"
    if ts:
        try:
            start_time_str = datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M")
        except Exception:
            start_time_str = str(ts)

    return {
        "run_id":             info.get("run_id", ""),
        "status":             info.get("status", ""),
        "start_time":         start_time_str,
        "start_time_raw":     ts,
        # ── Core Metrics (always present after training) ──────────────────
        "rmse":               metrics.get("rmse"),
        "mae":                metrics.get("mae"),
        "mape":               metrics.get("mape"),
        "best_trial":         metrics.get("best_trial"),
        "data_columns":       metrics.get("data_columns"),
        "data_missing_pct":   metrics.get("data_missing_pct"),
        "data_rows":          metrics.get("data_rows"),
        "ensemble_mae":       metrics.get("ensemble_mae"),
        "ensemble_rmse":      metrics.get("ensemble_rmse"),
        "feature_columns":    metrics.get("feature_columns"),
        "feature_rows":       metrics.get("feature_rows"),
        "num_features":       metrics.get("num_features"),
        "preprocessed_columns": metrics.get("preprocessed_columns"),
        "preprocessed_rows":  metrics.get("preprocessed_rows"),
        "rmse_improvement":   metrics.get("rmse_improvement"),
        # All raw metrics dict (for dynamic display of any extra tracked values)
        "all_metrics":        metrics,
        # ── Parameters (8 Optuna/training params) ─────────────────────────
        "params":             params,
        # Convenience aliases for common params
        "n_trials":           params.get("n_trials"),
        "train_fraction":     params.get("train_fraction"),
        "primary_model":      params.get("primary_model"),
        "ensemble_type":      params.get("ensemble_type"),
        # ── Tags / Metadata (12 tags) ─────────────────────────────────────
        "model_type":         tags.get("model_type", model_type),
        "model_version":      tags.get("model_version") or tags.get("mlflow.source.name", ""),
        "model_path":         tags.get("model_path", ""),
        "feature_count":      tags.get("feature_count", ""),
        "dataset_size":       tags.get("dataset_size", ""),
        "pipeline_version":   tags.get("pipeline_version", ""),
        "optimization":       tags.get("optimization", ""),
        "environment":        tags.get("environment", ""),
        "host":               tags.get("host", ""),
        "optuna_study_name":  tags.get("optuna_study_name", ""),
        "git_commit":         tags.get("git_commit", ""),
        "data_version":       tags.get("data_version", ""),
        "run_name":           tags.get("mlflow.runName", ""),
        # Raw tags dict for dynamic display
        "all_tags":           tags,
    }


def get_best_mlflow_run() -> dict | None:
    """Fetch the FINISHED run with the lowest RMSE."""
    try:
        exp_id = _mlflow_experiment_id()
        if not exp_id:
            return None

        result = _safe_post(
            f"{MLFLOW_URL}/api/2.0/mlflow/runs/search",
            payload={
                "experiment_ids": [exp_id],
                "max_results": 50,
                "order_by": ["metrics.rmse ASC"],
                "filter_string": "status = 'FINISHED'",
            },
        )
        if not result:
            return None

        runs = result.get("runs", [])
        if not runs:
            return None

        return _parse_run(runs[0])
    except Exception as e:
        logger.debug(f"get_best_mlflow_run failed: {e}")
        return None


def get_latest_mlflow_run() -> dict | None:
    """Fetch the most recently started FINISHED run (by start_time DESC)."""
    try:
        exp_id = _mlflow_experiment_id()
        if not exp_id:
            return None

        result = _safe_post(
            f"{MLFLOW_URL}/api/2.0/mlflow/runs/search",
            payload={
                "experiment_ids": [exp_id],
                "max_results": 1,
                "order_by": ["start_time DESC"],
                "filter_string": "status = 'FINISHED'",
            },
        )
        if not result:
            return None

        runs = result.get("runs", [])
        return _parse_run(runs[0]) if runs else None
    except Exception as e:
        logger.debug(f"get_latest_mlflow_run failed: {e}")
        return None


def get_mlflow_run_history(n: int = 5) -> list[dict]:
    """Return the last `n` FINISHED runs, most recent first."""
    try:
        exp_id = _mlflow_experiment_id()
        if not exp_id:
            return []

        result = _safe_post(
            f"{MLFLOW_URL}/api/2.0/mlflow/runs/search",
            payload={
                "experiment_ids": [exp_id],
                "max_results": n,
                "order_by": ["start_time DESC"],
                "filter_string": "status = 'FINISHED'",
            },
        )
        if not result:
            return []

        return [_parse_run(r) for r in result.get("runs", [])]
    except Exception as e:
        logger.debug(f"get_mlflow_run_history failed: {e}")
        return []


# ── Model Info & Feature Importance ──────────────────────────────────────────

def get_model_info() -> dict:
    """Fetch /model/info from the model server."""
    result = _safe_get(f"{MODEL_SERVER_URL}/model/info")
    return result or {}


def get_feature_importance() -> dict[str, float]:
    """Fetch feature importance from model server /model/info endpoint."""
    info = get_model_info()
    fi = info.get("feature_importances") or info.get("feature_importance") or {}
    if isinstance(fi, list) and info.get("features"):
        features = info["features"]
        fi = dict(zip(features, fi, strict=False))
    return fi

def get_shap_summary() -> dict:
    """Fetch the SHAP summary plot as a JSON serialized Plotly figure.
    Returns the raw JSON dictionary which can be loaded via plotly.io.from_json().
    """
    result = _safe_get(f"{MODEL_SERVER_URL}/explain/summary", timeout=SERVICE_TIMEOUT * 2)
    return result or {}


# ── Live Predictions ─────────────────────────────────────────────────────────

def send_prediction(features: dict) -> dict:
    """Send a prediction request to the live model server.

    Returns the response dict or a dict with an 'error' key on failure.
    Includes 'latency_ms' for tracking actual round-trip time.
    """
    import time
    try:
        start_t = time.time()
        resp = requests.post(
            f"{MODEL_SERVER_URL}/predict",
            json={"features": features},
            headers={"X-API-Key": MODEL_API_KEY, "Content-Type": "application/json"},
            timeout=SERVICE_TIMEOUT * 2,
        )
        latency = int((time.time() - start_t) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            data["latency_ms"] = latency
            return data
        return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:300], "latency_ms": latency}
    except Exception as e:
        return {"error": str(e)}


# Keep backward-compat alias used by predictions.py
def send_test_prediction(features: dict | None = None) -> dict | None:
    if features is None:
        features = {"temp": 0.5, "humidity": 0.65, "wind_speed": 0.15,
                    "hour": 14, "day_of_week": 3, "month": 6}
    result = send_prediction(features)
    return None if "error" in result else result
