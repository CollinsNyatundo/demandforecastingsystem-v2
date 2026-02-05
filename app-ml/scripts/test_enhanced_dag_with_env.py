#!/usr/bin/env python3
"""Test script to verify Enhanced DAG functionality with environment variables set."""

import os
import sys
from pathlib import Path

# Set environment variables directly for testing
os.environ["MLFLOW_TRACKING_URI"] = os.environ.get(
    "MLFLOW_TRACKING_URI", "http://mlflow:5000"
)
os.environ["MLFLOW_EXPERIMENT_NAME"] = os.environ.get(
    "MLFLOW_EXPERIMENT_NAME", "demand_forecasting"
)
os.environ["OPTUNA_STORAGE_URL"] = os.environ.get(
    "OPTUNA_STORAGE_URL", "postgresql://airflow:airflow@postgres:5432/optuna"
)
os.environ["OPTUNA_STUDY_NAME"] = os.environ.get(
    "OPTUNA_STUDY_NAME", "demand_forecasting_study"
)

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "dags"))


def test_enhanced_dag_import() -> bool | None:
    """Test that Enhanced DAG can be imported successfully."""
    try:
        from airflow_dag_enhanced import dag

        return True
    except ImportError:
        return False


def test_mlflow_connection() -> bool | None:
    """Test MLflow connection."""
    try:
        import mlflow

        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "demand_forecasting")
        mlflow.set_tracking_uri(tracking_uri)
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment:
            pass
        else:
            pass
        return True
    except Exception:
        return False


def test_optuna_postgresql() -> bool | None:
    """Test Optuna PostgreSQL connection."""
    try:
        import optuna
        from optuna.storages import RDBStorage

        storage_url = os.environ.get(
            "OPTUNA_STORAGE_URL", "postgresql://airflow:airflow@postgres:5432/optuna"
        )
        storage = RDBStorage(storage_url)
        optuna.create_study(
            storage=storage,
            study_name="test_study",
            direction="minimize",
            load_if_exists=True,
        )
        return True
    except Exception:
        return False


def test_catboost_import() -> bool | None:
    """Test CatBoost import."""
    try:
        from catboost import CatBoostRegressor

        return True
    except ImportError:
        return False


def test_environment_variables() -> bool:
    """Test required environment variables."""
    required_vars = [
        "MLFLOW_TRACKING_URI",
        "MLFLOW_EXPERIMENT_NAME",
        "OPTUNA_STORAGE_URL",
        "OPTUNA_STUDY_NAME",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    return not missing_vars


def main():
    """Run all tests."""
    tests = [
        ("Environment Variables", test_environment_variables),
        ("CatBoost Import", test_catboost_import),
        ("Enhanced DAG Import", test_enhanced_dag_import),
        ("MLflow Connection", test_mlflow_connection),
        ("Optuna PostgreSQL", test_optuna_postgresql),
    ]

    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))

    passed = 0
    total = len(results)

    for test_name, result in results:
        if result:
            passed += 1

    if passed == total:
        pass
    else:
        pass


if __name__ == "__main__":
    main()
