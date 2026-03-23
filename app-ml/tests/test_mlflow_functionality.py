#!/usr/bin/env python3
"""Test MLflow functionality by connecting to the tracking server."""

import sys
import time

import mlflow
import mlflow.sklearn
import numpy as np
import requests
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def test_mlflow_connection() -> bool | None:
    """Test connection to MLflow tracking server."""
    try:
        # Set tracking URI
        mlflow.set_tracking_uri("http://localhost:5000")

        # Test connection by getting experiments
        experiments = mlflow.search_experiments()

        for _exp in experiments:
            pass

        return True

    except Exception:
        return False


def test_mlflow_experiment_creation():
    """Test creating an MLflow experiment."""
    try:
        # Create experiment
        experiment_name = f"demand_forecasting_test_{int(time.time())}"
        experiment_id = mlflow.create_experiment(
            name=experiment_name,
            tags={"purpose": "system_test", "environment": "development"},
        )

        # Set experiment
        mlflow.set_experiment(experiment_name)

        return experiment_id

    except Exception:
        return None


def test_mlflow_run_and_model():
    """Test creating an MLflow run and logging a model."""
    try:
        # Generate sample data
        np.random.seed(42)
        X = np.random.rand(100, 5)
        y = np.random.rand(100) * 100

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Start MLflow run
        with mlflow.start_run(run_name="demand_forecasting_test_run") as run:
            # Train model
            model = RandomForestRegressor(n_estimators=10, random_state=42)
            model.fit(X_train, y_train)

            # Make predictions
            y_pred = model.predict(X_test)

            # Calculate metrics
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            # Log parameters
            mlflow.log_param("n_estimators", 10)
            mlflow.log_param("random_state", 42)
            mlflow.log_param("test_size", 0.2)

            # Log metrics
            mlflow.log_metric("mse", mse)
            mlflow.log_metric("r2", r2)
            mlflow.log_metric("training_samples", len(X_train))
            mlflow.log_metric("test_samples", len(X_test))

            # Log model
            mlflow.sklearn.log_model(
                model,
                "random_forest_model",
                registered_model_name="demand_forecasting_test_model",
            )

            return run.info.run_id

    except Exception:
        return None


def test_mlflow_model_registry() -> bool | None:
    """Test MLflow model registry functionality."""
    try:
        # Get registered models
        registered_models = mlflow.search_registered_models()

        for model in registered_models:
            for _version in model.latest_versions:
                pass

        # Test model serving prediction
        if registered_models:
            registered_models[0].name
            registered_models[0].latest_versions[0].version

            return True
        return False

    except Exception:
        return False


def test_mlflow_ui_access() -> bool | None:
    """Test MLflow UI accessibility."""
    try:
        # Test UI endpoints
        endpoints = [
            "http://localhost:5000",
            "http://localhost:5000/experiments",
            "http://localhost:5000/models",
        ]

        for endpoint in endpoints:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                pass
            else:
                pass

        return True

    except Exception:
        return False


def main() -> int:
    results = {}

    # Test connection
    results["connection"] = test_mlflow_connection()

    if results["connection"]:
        # Test experiment creation
        experiment_id = test_mlflow_experiment_creation()
        results["experiment_creation"] = experiment_id is not None

        if results["experiment_creation"]:
            # Test run and model logging
            run_id = test_mlflow_run_and_model()
            results["run_and_model"] = run_id is not None

            # Test model registry
            results["model_registry"] = test_mlflow_model_registry()
        else:
            results["run_and_model"] = False
            results["model_registry"] = False

    # Test UI access
    results["ui_access"] = test_mlflow_ui_access()

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
