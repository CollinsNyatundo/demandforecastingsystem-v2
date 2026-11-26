#!/usr/bin/env python3
import contextlib

import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error


def main() -> None:
    """Manual smoke test against a running local MLflow tracking container."""
    mlflow.set_tracking_uri("http://localhost:5000")

    with contextlib.suppress(BaseException):
        mlflow.create_experiment("container_test")

    mlflow.set_experiment("container_test")

    with mlflow.start_run(run_name="container_test_run"):
        X = np.random.rand(20, 2)
        y = np.random.rand(20)

        model = RandomForestRegressor(n_estimators=3, random_state=42)
        model.fit(X, y)

        y_pred = model.predict(X)
        mse = mean_squared_error(y, y_pred)

        mlflow.log_param("model_type", "RandomForest")
        mlflow.log_metric("mse", float(mse))
        mlflow.sklearn.log_model(model, "model")


if __name__ == "__main__":
    main()
