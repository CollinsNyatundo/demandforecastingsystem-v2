#!/usr/bin/env python3
"""Simple MLflow test without Unicode issues."""

import contextlib
import sys

import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def test_mlflow_simple() -> bool | None:
    """Simple MLflow test."""
    try:
        # Set tracking URI
        mlflow.set_tracking_uri("http://localhost:5000")

        # Create experiment
        experiment_name = "simple_test"
        with contextlib.suppress(Exception):
            mlflow.create_experiment(experiment_name)

        mlflow.set_experiment(experiment_name)

        # Generate sample data
        np.random.seed(42)
        X = np.random.rand(50, 3)
        y = np.random.rand(50) * 100

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Start run
        with mlflow.start_run(run_name="simple_rf_test"):
            # Train model
            model = RandomForestRegressor(n_estimators=5, random_state=42)
            model.fit(X_train, y_train)

            # Predict
            y_pred = model.predict(X_test)

            # Metrics
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            # Log without Unicode
            mlflow.log_param("model_type", "RandomForest")
            mlflow.log_param("n_estimators", 5)
            mlflow.log_metric("mse", float(mse))
            mlflow.log_metric("r2", float(r2))

            # Log model
            mlflow.sklearn.log_model(model, "model")


            return True

    except Exception:
        return False


def test_model_registry() -> bool | None:
    """Test model registry."""
    try:
        # List registered models
        models = mlflow.search_registered_models()

        # Register a model
        with mlflow.start_run():
            # Simple model
            X = np.random.rand(20, 2)
            y = np.random.rand(20)

            model = RandomForestRegressor(n_estimators=3, random_state=42)
            model.fit(X, y)

            # Register model
            mlflow.sklearn.log_model(
                model, "model", registered_model_name="test_demand_model"
            )


        # Check registry again
        models = mlflow.search_registered_models()

        for model in models:
            pass

        return True

    except Exception:
        return False


def main() -> int:

    # Test basic functionality
    result1 = test_mlflow_simple()

    # Test registry
    result2 = test_model_registry()


    if result1 and result2:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
