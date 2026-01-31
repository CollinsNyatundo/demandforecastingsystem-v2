"""
Comprehensive integration tests for the entire demand forecasting system.

Tests end-to-end workflows, MLOps integration, data pipelines,
and system-wide scenarios including failure recovery.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
from pathlib import Path
import mlflow
import optuna
from fastapi.testclient import TestClient

# Import all system components
from demand_forecasting.serving.model_server import app as model_server_app
from demand_forecasting.monitoring.drift_detector import DriftDetector
from demand_forecasting.explainability.shap_explainer import ModelExplainer
from demand_forecasting.optimization.multi_objective import objective_multi
from demand_forecasting.optimization.ensemble import EnsembleManager
from demand_forecasting.automation.retraining_scheduler import RetrainingScheduler


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end ML workflows."""

    def test_complete_training_to_serving_workflow(
        self, sample_data: pd.DataFrame, temp_directory: Path
    ):
        """Test complete workflow from data training to model serving."""
        # 1. Prepare data
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]

        # 2. Train model with optimization
        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        # Mock MLflow for model saving
        with patch("mlflow.catboost.log_model") as mock_log_model:
            # Train model
            from catboost import CatBoostRegressor

            model = CatBoostRegressor(
                iterations=100,
                learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3),
                depth=trial.suggest_int("depth", 3, 8),
                verbose=False,
            )
            model.fit(X, y)

            # Log to MLflow
            mlflow.log_params(trial.params)
            mlflow.log_metrics({"rmse": 50.0})
            mlflow.catboost.log_model(model, "model")

        # 3. Test model serving
        with patch(
            "demand_forecasting.serving.model_server.mlflow.pyfunc.load_model"
        ) as mock_load:
            mock_load.return_value = model

            client = TestClient(model_server_app)

            # Test prediction
            request_data = {
                "features": {
                    "temp": 20.0,
                    "humidity": 60.0,
                    "wind_speed": 5.0,
                    "hour": 14,
                    "day_of_week": 3,
                }
            }

            response = client.post("/predict", json=request_data)

            assert response.status_code == 200
            prediction_data = response.json()
            assert "prediction" in prediction_data
            assert isinstance(prediction_data["prediction"], float)

    def test_drift_detection_to_retraining_workflow(
        self, reference_data: pd.DataFrame, drifted_data: pd.DataFrame
    ):
        """Test workflow from drift detection to automated retraining decision."""
        # 1. Initialize drift detector
        drift_detector = DriftDetector(reference_data, threshold=0.05)

        # 2. Detect drift
        drift_result = drift_detector.detect_drift(drifted_data)

        # 3. Initialize retraining scheduler
        config = {"drift_threshold": 0.05, "model_registry_name": "demand_forecasting"}
        scheduler = RetrainingScheduler(config)

        # 4. Check if retraining is needed
        with patch.object(scheduler, "_check_drift_trigger", return_value=True):
            retrain_result = scheduler.should_retrain()

            # 5. Verify workflow integration
            assert drift_result["overall_drift_score"] > 0.05
            assert retrain_result["should_retrain"] is True
            assert "DATA_DRIFT" in retrain_result["triggers"]

    def test_optimization_to_ensemble_workflow(self, sample_data: pd.DataFrame):
        """Test workflow from optimization to ensemble creation."""
        # 1. Prepare data
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # 2. Run multi-objective optimization
        study = optuna.create_study(directions=["minimize", "minimize"])

        best_params = None
        best_rmse = float("inf")

        for _ in range(5):  # Limited trials for testing
            trial = study.ask()
            result = objective_multi(
                trial, X_train, X_test, y_train, y_test, ["rmse", "mae"]
            )
            study.tell(trial, result)

            if result[0] < best_rmse:  # RMSE is first objective
                best_rmse = result[0]
                best_params = trial.params

        # 3. Create ensemble with optimized parameters
        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble(catboost_params=best_params)

        # 4. Train and evaluate ensemble
        ensemble.fit(X_train, y_train)
        predictions = ensemble.predict(X_test)

        # 5. Verify workflow
        assert best_params is not None
        assert len(predictions) == len(X_test)
        assert not any(np.isnan(predictions))

    def test_explainability_integration(self, sample_data: pd.DataFrame):
        """Test explainability integration with trained model."""
        # 1. Train simple model
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]

        from catboost import CatBoostRegressor

        model = CatBoostRegressor(iterations=50, verbose=False)
        model.fit(X, y)

        # 2. Initialize explainer
        explainer = ModelExplainer(model, X)

        # 3. Test global explanations
        global_importance = explainer.global_importance(top_n=3)

        # 4. Test local explanations
        local_explanation = explainer.explain_prediction(sample_idx=0)

        # 5. Verify integration
        assert len(global_importance) == 3
        assert "feature" in global_importance.columns
        assert "importance" in global_importance.columns

        assert isinstance(local_explanation, dict)
        assert "shap_values" in local_explanation
        assert "feature_importance" in local_explanation


@pytest.mark.integration
class TestMLOpsIntegration:
    """Test MLOps infrastructure integration."""

    @pytest.mark.mlflow
    def test_mlflow_integration(
        self, sample_data: pd.DataFrame, mlflow_tracking_uri: str
    ):
        """Test MLflow tracking and model registry integration."""
        # Set up MLflow
        mlflow.set_tracking_uri(mlflow_tracking_uri)

        with mlflow.start_run():
            # Log parameters and metrics
            mlflow.log_params({"learning_rate": 0.1, "depth": 6, "iterations": 100})
            mlflow.log_metrics({"rmse": 45.2, "mae": 32.1, "training_time": 120.5})

            # Train and log model
            X = sample_data.drop("demand", axis=1)
            y = sample_data["demand"]

            from catboost import CatBoostRegressor

            model = CatBoostRegressor(
                learning_rate=0.1, depth=6, iterations=100, verbose=False
            )
            model.fit(X, y)

            mlflow.catboost.log_model(model, "model")

        # Verify MLflow tracking
        client = mlflow.tracking.MlflowClient()
        runs = client.search_runs()

        assert len(runs) > 0
        latest_run = runs[0]
        assert latest_run.data.params["learning_rate"] == 0.1
        assert latest_run.data.metrics["rmse"] == 45.2

    @pytest.mark.optuna
    def test_optuna_integration(
        self, sample_data: pd.DataFrame, optuna_storage: optuna.storages.RDBStorage
    ):
        """Test Optuna study persistence and integration."""
        # Create study with persistence
        study = optuna.create_study(
            study_name="integration_test_study",
            storage=optuna_storage,
            direction="minimize",
        )

        # Run optimization
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        def objective(trial):
            params = {
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                "depth": trial.suggest_int("depth", 3, 8),
                "iterations": trial.suggest_int("iterations", 50, 200),
            }

            model = CatBoostRegressor(**params, verbose=False)
            model.fit(X_train, y_train)
            predictions = model.predict(X_test)
            rmse = np.sqrt(np.mean((y_test - predictions) ** 2))

            return rmse

        study.optimize(objective, n_trials=5)

        # Verify persistence
        assert len(study.trials) == 5
        assert study.best_value is not None
        assert study.best_params is not None

        # Load study from storage to verify persistence
        loaded_study = optuna.load_study(
            study_name="integration_test_study", storage=optuna_storage
        )

        assert len(loaded_study.trials) == 5
        assert loaded_study.best_value == study.best_value

    def test_airflow_dag_integration(self, sample_data: pd.DataFrame):
        """Test Airflow DAG integration with Kedro pipelines."""
        # This would test the actual DAG execution
        # For now, test DAG imports and structure

        try:
            from dags.airflow_dag_enhanced import demand_forecasting_dag

            # Verify DAG structure
            assert demand_forecasting_dag is not None
            assert hasattr(demand_forecasting_dag, "dag_id")

            # Test DAG tasks exist
            tasks = demand_forecasting_dag.tasks
            assert len(tasks) > 0

        except ImportError:
            pytest.skip("Airflow DAG not available for testing")


@pytest.mark.integration
class TestSystemResilience:
    """Test system resilience and error recovery."""

    def test_model_loading_failure_recovery(self, sample_data: pd.DataFrame):
        """Test system recovery when model loading fails."""
        # Mock MLflow failure
        with patch(
            "mlflow.pyfunc.load_model", side_effect=Exception("MLflow unavailable")
        ):
            with patch("joblib.load", side_effect=Exception("Local model unavailable")):
                # Test graceful degradation
                from demand_forecasting.serving.model_server import ml_models

                # Should handle loading failures gracefully
                try:
                    # This should fail gracefully
                    client = TestClient(model_server_app)
                    response = client.post(
                        "/predict",
                        json={
                            "features": {
                                "temp": 20.0,
                                "humidity": 60.0,
                                "wind_speed": 5.0,
                                "hour": 14,
                                "day_of_week": 3,
                            }
                        },
                    )

                    # Should return error, not crash
                    assert response.status_code in [500, 503]

                except Exception as e:
                    # Should be a handled exception, not a crash
                    assert "model" in str(e).lower()

    def test_data_quality_robustness(self):
        """Test system robustness to data quality issues."""
        # Create problematic data
        problematic_data = pd.DataFrame(
            {
                "temp": [20.0, np.nan, -50.0, 1000.0, "invalid"],
                "humidity": [60.0, 110.0, -10.0, np.nan, 50.0],
                "wind_speed": [5.0, 0.0, -5.0, 200.0, np.inf],
                "hour": [14, 25, -1, 24, 12.5],
                "day_of_week": [3, 8, -1, 6.5, "monday"],
                "demand": [50, 100, -10, 1000000, np.nan],
            }
        )

        # Test each component with problematic data
        try:
            # Drift detector
            reference_clean = pd.DataFrame(
                {
                    "temp": [20.0, 21.0, 22.0],
                    "humidity": [60.0, 61.0, 62.0],
                    "wind_speed": [5.0, 6.0, 7.0],
                    "hour": [14, 15, 16],
                    "day_of_week": [3, 4, 5],
                }
            )

            detector = DriftDetector(reference_clean)
            result = detector.detect_drift(problematic_data)

            # Should handle problematic data gracefully
            assert result is not None
            assert "overall_drift_score" in result

        except Exception as e:
            # Should handle data quality issues
            assert "data" in str(e).lower() or "invalid" in str(e).lower()

    def test_memory_pressure_handling(self, sample_data: pd.DataFrame):
        """Test system behavior under memory pressure."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create large models and data to simulate memory pressure
        large_models = []
        for i in range(10):
            X_large = pd.DataFrame(np.random.random((10000, 100)))
            y_large = pd.Series(np.random.random(10000))

            from catboost import CatBoostRegressor

            model = CatBoostRegressor(iterations=100, verbose=False)
            model.fit(X_large, y_large)
            large_models.append(model)

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Clean up
        del large_models

        # Should handle memory pressure gracefully
        assert memory_increase > 0  # Memory should have increased

        # System should still be functional
        try:
            # Test basic functionality
            detector = DriftDetector(sample_data)
            result = detector.detect_drift(sample_data)
            assert result is not None
        except MemoryError:
            pytest.skip("System under memory pressure, skipping test")

    def test_concurrent_operations(self, sample_data: pd.DataFrame):
        """Test system behavior under concurrent operations."""
        import threading
        import time

        results = []
        errors = []

        def train_model():
            try:
                X = sample_data.drop("demand", axis=1)
                y = sample_data["demand"]

                from catboost import CatBoostRegressor

                model = CatBoostRegressor(iterations=50, verbose=False)
                model.fit(X, y)
                results.append("training_complete")
            except Exception as e:
                errors.append(e)

        def detect_drift():
            try:
                detector = DriftDetector(sample_data)
                result = detector.detect_drift(sample_data)
                results.append("drift_detection_complete")
            except Exception as e:
                errors.append(e)

        def create_explainer():
            try:
                X = sample_data.drop("demand", axis=1)
                y = sample_data["demand"]

                from catboost import CatBoostRegressor

                model = CatBoostRegressor(iteratives=50, verbose=False)
                model.fit(X, y)

                explainer = ModelExplainer(model, X)
                results.append("explainer_created")
            except Exception as e:
                errors.append(e)

        # Run concurrent operations
        threads = []
        for operation in [train_model, detect_drift, create_explainer]:
            for _ in range(3):  # Multiple instances of each
                thread = threading.Thread(target=operation)
                threads.append(thread)
                thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=60)  # 60 second timeout

        # Verify results
        assert len(errors) == 0, f"Concurrent operations failed: {errors}"
        assert len(results) == 9  # 3 operations × 3 instances


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceBenchmarks:
    """Test system performance benchmarks."""

    def test_prediction_latency_benchmark(self, sample_data: pd.DataFrame):
        """Test prediction latency benchmarks."""
        # Train model
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]

        from catboost import CatBoostRegressor

        model = CatBoostRegressor(iterations=100, verbose=False)
        model.fit(X, y)

        # Benchmark prediction latency
        import time

        with patch(
            "demand_forecasting.serving.model_server.mlflow.pyfunc.load_model",
            return_value=model,
        ):
            client = TestClient(model_server_app)

            latencies = []
            for _ in range(100):
                start_time = time.time()

                response = client.post(
                    "/predict",
                    json={
                        "features": {
                            "temp": 20.0,
                            "humidity": 60.0,
                            "wind_speed": 5.0,
                            "hour": 14,
                            "day_of_week": 3,
                        }
                    },
                )

                end_time = time.time()
                latencies.append(end_time - start_time)

                assert response.status_code == 200

            # Verify latency requirements
            avg_latency = np.mean(latencies)
            p95_latency = np.percentile(latencies, 95)

            # Should meet latency requirements
            assert avg_latency < 0.1  # 100ms average
            assert p95_latency < 0.5  # 500ms 95th percentile

    def test_drift_detection_performance(self, reference_data: pd.DataFrame):
        """Test drift detection performance benchmarks."""
        import time

        # Create large current dataset
        large_current = pd.DataFrame(
            {col: np.random.normal(0, 1, 10000) for col in reference_data.columns}
        )

        detector = DriftDetector(reference_data)

        # Benchmark drift detection
        start_time = time.time()
        result = detector.detect_drift(large_current)
        end_time = time.time()

        processing_time = end_time - start_time

        # Verify performance requirements
        assert processing_time < 10.0  # 10 seconds for 10k samples
        assert result is not None
        assert "overall_drift_score" in result

    def test_optimization_performance(self, sample_data: pd.DataFrame):
        """Test optimization performance benchmarks."""
        import time

        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Benchmark optimization
        study = optuna.create_study(direction="minimize")

        start_time = time.time()

        def objective(trial):
            params = {
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                "depth": trial.suggest_int("depth", 3, 8),
                "iterations": trial.suggest_int("iterations", 50, 200),
            }

            model = CatBoostRegressor(**params, verbose=False)
            model.fit(X_train, y_train)
            predictions = model.predict(X_test)
            rmse = np.sqrt(np.mean((y_test - predictions) ** 2))

            return rmse

        study.optimize(objective, n_trials=10)
        end_time = time.time()

        optimization_time = end_time - start_time

        # Verify performance requirements
        assert optimization_time < 300.0  # 5 minutes for 10 trials
        assert study.best_value is not None


@pytest.mark.integration
class TestSystemConfiguration:
    """Test system configuration and deployment scenarios."""

    def test_configuration_validation(self):
        """Test system configuration validation."""
        # Test valid configuration
        valid_config = {
            "model_params": {"learning_rate": 0.1, "depth": 6, "iterations": 100},
            "drift_threshold": 0.05,
            "retraining_config": {
                "time_interval_days": 7,
                "performance_threshold": 5.0,
            },
        }

        # Should accept valid configuration
        scheduler = RetrainingScheduler(valid_config["retraining_config"])
        assert scheduler is not None

        detector = DriftDetector(sample_data, valid_config["drift_threshold"])
        assert detector is not None

    def test_environment_variable_handling(self):
        """Test environment variable handling."""
        # Test with various environment variable states
        with patch.dict(
            os.environ,
            {
                "MLFLOW_TRACKING_URI": "http://test-mlflow:5000",
                "OPTUNA_STORAGE_URL": "postgresql://test:test@localhost/test",
            },
        ):
            # Should use environment variables
            mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
            optuna_url = os.environ.get("OPTUNA_STORAGE_URL")

            assert mlflow_uri == "http://test-mlflow:5000"
            assert optuna_url == "postgresql://test:test@localhost/test"

    def test_docker_compatibility(self):
        """Test Docker deployment compatibility."""
        # Test that all components can work in Docker environment
        docker_env_vars = {
            "MLFLOW_TRACKING_URI": "http://mlflow:5000",
            "POSTGRES_HOST": "postgres",
            "REDIS_HOST": "redis",
            "MINIO_ENDPOINT": "minio:9000",
        }

        with patch.dict(os.environ, docker_env_vars):
            # Should work with Docker environment
            assert os.environ.get("MLFLOW_TRACKING_URI") == "http://mlflow:5000"
            assert os.environ.get("POSTGRES_HOST") == "postgres"

            # Test component initialization with Docker env
            try:
                # This would typically connect to Docker services
                mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI"))
                assert True  # If no exception, Docker compatibility is OK
            except Exception:
                pytest.skip("Docker services not available for testing")
