#!/usr/bin/env python3
"""
Simple MLflow test without Unicode issues
"""

import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import sys


def test_mlflow_simple():
    """Simple MLflow test"""
    print("Testing MLflow functionality...")

    try:
        # Set tracking URI
        mlflow.set_tracking_uri("http://localhost:5000")

        # Create experiment
        experiment_name = "simple_test"
        try:
            mlflow.create_experiment(experiment_name)
            print(f"Created experiment: {experiment_name}")
        except Exception:
            print(f"Experiment {experiment_name} already exists")

        mlflow.set_experiment(experiment_name)

        # Generate sample data
        np.random.seed(42)
        X = np.random.rand(50, 3)
        y = np.random.rand(50) * 100

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Start run
        with mlflow.start_run(run_name="simple_rf_test") as run:
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

            print(f"Run completed: {run.info.run_id}")
            print(f"MSE: {mse:.4f}")
            print(f"R2: {r2:.4f}")

            return True

    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_model_registry():
    """Test model registry"""
    print("\nTesting model registry...")

    try:
        # List registered models
        models = mlflow.search_registered_models()
        print(f"Found {len(models)} registered models")

        # Register a model
        with mlflow.start_run() as run:
            # Simple model
            X = np.random.rand(20, 2)
            y = np.random.rand(20)

            model = RandomForestRegressor(n_estimators=3, random_state=42)
            model.fit(X, y)

            # Register model
            mlflow.sklearn.log_model(
                model, "model", registered_model_name="test_demand_model"
            )

        print("Model registered successfully")

        # Check registry again
        models = mlflow.search_registered_models()
        print(f"Now found {len(models)} registered models")

        for model in models:
            print(f"  - {model.name}")

        return True

    except Exception as e:
        print(f"Registry error: {str(e)}")
        return False


def main():
    print("=" * 50)
    print("SIMPLE MLFLOW TEST")
    print("=" * 50)

    # Test basic functionality
    result1 = test_mlflow_simple()

    # Test registry
    result2 = test_model_registry()

    print("\n" + "=" * 50)
    print("RESULTS:")
    print(f"Basic MLflow: {'PASS' if result1 else 'FAIL'}")
    print(f"Model Registry: {'PASS' if result2 else 'FAIL'}")

    if result1 and result2:
        print("\nAll MLflow tests PASSED!")
        return 0
    else:
        print("\nSome MLflow tests FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
