#!/usr/bin/env python3
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor

# Set tracking URI
mlflow.set_tracking_uri("http://localhost:5000")

# Create experiment for registry test
mlflow.set_experiment("model_registry_test")

# Start run and register model
with mlflow.start_run(run_name="registry_test_run") as run:
    # Simple model
    X = np.random.rand(20, 2)
    y = np.random.rand(20)

    model = RandomForestRegressor(n_estimators=3, random_state=42)
    model.fit(X, y)

    # Register model
    mlflow.sklearn.log_model(
        model, "model", registered_model_name="demand_forecasting_test_model"
    )


# Test model registry functionality
try:
    from mlflow.tracking import MlflowClient

    client = MlflowClient()

    # List registered models
    models = client.search_registered_models()

    for model in models:
        for _version in model.latest_versions:
            pass


except Exception:
    pass
