#!/usr/bin/env python3
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor


def main() -> None:
    """Manual smoke test against a running local MLflow Model Registry."""
    mlflow.set_tracking_uri("http://localhost:5000")
    mlflow.set_experiment("model_registry_test")

    with mlflow.start_run(run_name="registry_test_run"):
        X = np.random.rand(20, 2)
        y = np.random.rand(20)

        model = RandomForestRegressor(n_estimators=3, random_state=42)
        model.fit(X, y)

        mlflow.sklearn.log_model(
            model, "model", registered_model_name="demand_forecasting_test_model"
        )

    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        models = client.search_registered_models()
        for model in models:
            for _version in model.latest_versions:
                pass
    except Exception:
        pass


if __name__ == "__main__":
    main()
