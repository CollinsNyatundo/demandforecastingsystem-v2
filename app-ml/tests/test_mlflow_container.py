#!/usr/bin/env python3
import contextlib

import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error

# Set tracking URI
mlflow.set_tracking_uri("http://localhost:5000")

# Create experiment
with contextlib.suppress(BaseException):
    mlflow.create_experiment("container_test")

mlflow.set_experiment("container_test")

# Start run
with mlflow.start_run(run_name="container_test_run") as run:
    # Simple model
    X = np.random.rand(20, 2)
    y = np.random.rand(20)

    model = RandomForestRegressor(n_estimators=3, random_state=42)
    model.fit(X, y)

    # Log metrics
    y_pred = model.predict(X)
    mse = mean_squared_error(y, y_pred)

    mlflow.log_param("model_type", "RandomForest")
    mlflow.log_metric("mse", float(mse))

    # Log model
    mlflow.sklearn.log_model(model, "model")
