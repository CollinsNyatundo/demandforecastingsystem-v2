"""
Comprehensive test configuration for app-ml demand forecasting system.

Provides fixtures and utilities for testing all system components including:
- ML models and pipelines
- FastAPI endpoints
- Data processing and validation
- MLOps infrastructure (MLflow, Optuna, Airflow)
- Edge cases and error scenarios
"""

import shutil
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Import required modules
from demand_forecasting.monitoring.drift_detector import DriftDetector
from demand_forecasting.optimization.ensemble import EnsembleManager

# Import pytest fixtures only when available
try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

# Import system components only when available
try:
    from unittest.mock import MagicMock, Mock, patch

    import mlflow
    import numpy as np
    import optuna
    import pandas as pd
    from fastapi.testclient import TestClient
    from optuna.storages import RDBStorage

    from demand_forecasting.automation.retraining_scheduler import RetrainingScheduler
    from demand_forecasting.explainability.shap_explainer import ModelExplainer
    from demand_forecasting.monitoring.drift_detector import DriftDetector
    from demand_forecasting.optimization.ensemble import EnsembleManager
    from demand_forecasting.optimization.multi_objective import objective_multi
    from demand_forecasting.serving.model_router import ModelRouter

    # Import system components
    from demand_forecasting.serving.model_server import app as model_server_app

    COMPONENTS_AVAILABLE = True
except ImportError:
    COMPONENTS_AVAILABLE = False


@pytest.fixture(scope="session")
def test_config() -> dict[str, Any]:
    """Test configuration for all components."""
    return {
        "model_params": {
            "learning_rate": 0.1,
            "depth": 6,
            "l2_leaf_reg": 3.0,
            "iterations": 100,
            "verbose": False,
            "random_state": 42,
        },
        "drift_threshold": 0.05,
        "retraining_config": {
            "time_interval_days": 7,
            "performance_threshold": 5.0,
            "data_volume_threshold": 10000,
            "drift_threshold": 0.1,
            "model_registry_name": "demand_forecasting",
        },
        "optuna_storage": "sqlite:///test_optuna.db",
        "mlflow_tracking_uri": "sqlite:///test_mlflow.db",
    }


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """Generate sample demand forecasting data for testing."""
    np.random.seed(42)
    n_samples = 1000

    data = {
        "temp": np.random.normal(20, 10, n_samples),
        "humidity": np.random.normal(60, 20, n_samples),
        "wind_speed": np.random.exponential(5, n_samples),
        "hour": np.random.randint(0, 24, n_samples),
        "day_of_week": np.random.randint(0, 7, n_samples),
        "demand": np.random.poisson(50, n_samples),
    }

    # Ensure realistic ranges
    data["temp"] = np.clip(data["temp"], -10, 40)
    data["humidity"] = np.clip(data["humidity"], 0, 100)
    data["wind_speed"] = np.clip(data["wind_speed"], 0, 30)

    return pd.DataFrame(data)


@pytest.fixture
def reference_data() -> pd.DataFrame:
    """Reference data for drift detection testing."""
    np.random.seed(123)
    n_samples = 500

    data = {
        "temp": np.random.normal(22, 8, n_samples),
        "humidity": np.random.normal(55, 15, n_samples),
        "wind_speed": np.random.exponential(4, n_samples),
        "hour": np.random.randint(0, 24, n_samples),
        "day_of_week": np.random.randint(0, 7, n_samples),
    }

    return pd.DataFrame(data)


@pytest.fixture
def drifted_data() -> pd.DataFrame:
    """Data with drift for testing drift detection."""
    np.random.seed(456)
    n_samples = 500

    # Create drifted distribution
    data = {
        "temp": np.random.normal(30, 5, n_samples),  # Shifted mean
        "humidity": np.random.normal(80, 10, n_samples),  # Shifted mean
        "wind_speed": np.random.exponential(8, n_samples),  # Different scale
        "hour": np.random.randint(0, 24, n_samples),
        "day_of_week": np.random.randint(0, 7, n_samples),
    }

    return pd.DataFrame(data)


@pytest.fixture
def sample_model():
    """Create a simple mock model for testing."""

    class MockModel:
        def predict(self, X):
            if isinstance(X, np.ndarray):
                return np.random.normal(50, 10, len(X))
            return np.random.normal(50, 10, 1)

        def fit(self, X, y):
            return self

    return MockModel()


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for test artifacts."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mlflow_tracking_uri(temp_directory: Path) -> str:
    """MLflow tracking URI for testing."""
    uri = f"sqlite:///{temp_directory}/test_mlflow.db"
    mlflow.set_tracking_uri(uri)
    return uri


@pytest.fixture
def optuna_storage(temp_directory: Path) -> RDBStorage:
    """Optuna storage for testing."""
    storage_url = f"sqlite:///{temp_directory}/test_optuna.db"
    return RDBStorage(storage_url)


@pytest.fixture
def mock_mlflow_client():
    """Mock MLflow client for testing."""
    with patch("mlflow.tracking.MlflowClient") as mock_client:
        client = Mock()
        mock_client.return_value = client

        # Mock common methods
        client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=pd.Timestamp.now())
        ]
        client.get_run.return_value = Mock(
            data=Mock(metrics={"rmse": 50.0, "mae": 30.0})
        )

        yield client


@pytest.fixture
def model_server_test_client() -> TestClient:
    """Test client for model server FastAPI app."""
    return TestClient(model_server_app)


@pytest.fixture
def drift_detector(
    reference_data: pd.DataFrame, test_config: dict[str, Any]
) -> DriftDetector:
    """Drift detector instance for testing."""
    return DriftDetector(
        reference_data=reference_data, threshold=test_config["drift_threshold"]
    )


@pytest.fixture
def ensemble_manager() -> EnsembleManager:
    """Ensemble manager for testing."""
    return EnsembleManager()


@pytest.fixture
def retraining_scheduler(test_config: dict[str, Any]) -> RetrainingScheduler:
    """Retraining scheduler for testing."""
    return RetrainingScheduler(test_config["retraining_config"])


@pytest.fixture(
    params=[
        "normal_case",
        "missing_features",
        "invalid_types",
        "extreme_values",
        "empty_data",
        "single_row",
        "duplicate_rows",
        "null_values",
        "negative_values",
        "large_values",
    ]
)
def test_scenarios(request):
    """Parametrized test scenarios for edge cases."""
    return request.param


@pytest.fixture
def edge_case_data(test_scenarios: str, sample_data: pd.DataFrame) -> pd.DataFrame:
    """Generate edge case data based on scenario."""
    data = sample_data.copy()

    if test_scenarios == "missing_features":
        # Remove essential features
        data = data.drop(columns=["temp", "humidity"])

    elif test_scenarios == "invalid_types":
        # Add invalid data types
        data.loc[0, "temp"] = "invalid"
        data.loc[1, "humidity"] = None

    elif test_scenarios == "extreme_values":
        # Add extreme but valid values
        data.loc[0, "temp"] = 100.0  # Very hot
        data.loc[1, "temp"] = -50.0  # Very cold
        data.loc[2, "wind_speed"] = 100.0  # Extreme wind

    elif test_scenarios == "empty_data":
        # Return empty DataFrame
        return pd.DataFrame(columns=data.columns)

    elif test_scenarios == "single_row":
        # Return single row
        return data.iloc[0:1]

    elif test_scenarios == "duplicate_rows":
        # Add duplicates
        data = pd.concat([data, data.iloc[0:5]], ignore_index=True)

    elif test_scenarios == "null_values":
        # Add null values
        for col in ["temp", "humidity", "wind_speed"]:
            data.loc[data.sample(frac=0.1).index, col] = np.nan

    elif test_scenarios == "negative_values":
        # Add negative values where inappropriate
        data.loc[0, "demand"] = -10  # Negative demand

    elif test_scenarios == "large_values":
        # Add very large values
        data.loc[0, "demand"] = 1000000  # Very large demand

    return data


# Pytest hooks and configuration
def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow integration tests",
    )
    parser.addoption(
        "--run-mlflow",
        action="store_true",
        default=False,
        help="Run tests that require MLflow",
    )
    parser.addoption(
        "--run-optuna",
        action="store_true",
        default=False,
        help="Run tests that require Optuna",
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "mlflow: marks tests that require MLflow")
    config.addinivalue_line("markers", "optuna: marks tests that require Optuna")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "edge_case: marks tests that cover edge cases")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on command line options."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

    if not config.getoption("--run-mlflow"):
        skip_mlflow = pytest.mark.skip(reason="need --run-mlflow option to run")
        for item in items:
            if "mlflow" in item.keywords:
                item.add_marker(skip_mlflow)

    if not config.getoption("--run-optuna"):
        skip_optuna = pytest.mark.skip(reason="need --run-optuna option to run")
        for item in items:
            if "optuna" in item.keywords:
                item.add_marker(skip_optuna)
