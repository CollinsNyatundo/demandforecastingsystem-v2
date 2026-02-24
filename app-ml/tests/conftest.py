"""
Comprehensive test configuration for app-ml demand forecasting system.

Provides fixtures and utilities for testing all system components including:
- ML models and pipelines
- FastAPI endpoints
- Data processing and validation
- MLOps infrastructure (MLflow, Optuna, Airflow)
- Edge cases and error scenarios
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Import pytest fixtures only when available
try:
    import pytest  # type: ignore[import-not-found]

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

# Initialize module-level variables for lazy imports
DriftDetector = None
EnsembleManager = None
RetrainingScheduler = None
ModelExplainer = None
ModelRouter = None
model_server_app = None
mlflow = None
RDBStorage = None
np = None
pd = None
TestClient = None
Mock = None
MagicMock = None
patch = None

COMPONENTS_AVAILABLE = False

# Import system components only when available (lazy loading pattern)
try:
    from unittest.mock import MagicMock, Mock, patch

    import mlflow  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]
    import pandas as pd  # type: ignore[import-not-found]
    from fastapi.testclient import TestClient  # type: ignore[import-not-found]
    from optuna.storages import RDBStorage  # type: ignore[import-not-found]

    from demand_forecasting.automation.retraining_scheduler import (
        RetrainingScheduler,  # type: ignore[import-not-found]
    )
    from demand_forecasting.explainability.shap_explainer import (
        ModelExplainer,  # type: ignore[import-not-found]
    )
    from demand_forecasting.monitoring.drift_detector import (
        DriftDetector,  # type: ignore[import-not-found]
    )
    from demand_forecasting.optimization.ensemble import (
        EnsembleManager,  # type: ignore[import-not-found]
    )
    from demand_forecasting.optimization.multi_objective import (
        objective_multi,  # type: ignore[import-not-found]
    )
    from demand_forecasting.serving.model_router import (
        ModelRouter,  # type: ignore[import-not-found]
    )

    # Import model server app (may fail if dependencies not met)
    try:
        from demand_forecasting.serving.model_server import (
            app as model_server_app,  # type: ignore[import-not-found]
        )
    except ImportError:
        model_server_app = None

    COMPONENTS_AVAILABLE = True
except ImportError as e:
    import warnings

    warnings.warn(f"Some test dependencies not available: {e}")
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
def sample_data():
    """Generate sample demand forecasting data for testing."""
    if np is None or pd is None:
        pytest.skip("numpy or pandas not available")
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
def reference_data():
    """Reference data for drift detection testing."""
    if np is None or pd is None:
        pytest.skip("numpy or pandas not available")
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
def drifted_data():
    """Data with drift for testing drift detection."""
    if np is None or pd is None:
        pytest.skip("numpy or pandas not available")
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
    if np is None:
        pytest.skip("numpy not available")

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
    if mlflow is None:
        pytest.skip("mlflow not available")
    uri = f"sqlite:///{temp_directory}/test_mlflow.db"
    mlflow.set_tracking_uri(uri)
    return uri


@pytest.fixture
def optuna_storage(temp_directory: Path):
    """Optuna storage for testing."""
    if RDBStorage is None:
        pytest.skip("optuna not available")
    storage_url = f"sqlite:///{temp_directory}/test_optuna.db"
    return RDBStorage(storage_url)


@pytest.fixture
def mock_mlflow_client():
    """Mock MLflow client for testing."""
    if patch is None or Mock is None or pd is None:
        pytest.skip("unittest.mock or pandas not available")
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
def model_server_test_client():
    """Test client for model server FastAPI app."""
    if TestClient is None or model_server_app is None:
        pytest.skip("model_server or TestClient not available")
    return TestClient(model_server_app)


@pytest.fixture
def drift_detector(reference_data, test_config: dict[str, Any]):
    """Drift detector instance for testing."""
    if DriftDetector is None:
        pytest.skip("DriftDetector not available")
    return DriftDetector(
        reference_data=reference_data, threshold=test_config["drift_threshold"]
    )


@pytest.fixture
def ensemble_manager():
    """Ensemble manager for testing."""
    if EnsembleManager is None:
        pytest.skip("EnsembleManager not available")
    return EnsembleManager()


@pytest.fixture
def retraining_scheduler(test_config: dict[str, Any]):
    """Retraining scheduler for testing."""
    if RetrainingScheduler is None:
        pytest.skip("RetrainingScheduler not available")
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


# Helper functions for edge case scenarios to reduce complexity
def _apply_missing_features(data: pd.DataFrame) -> pd.DataFrame:
    """Remove essential features."""
    return data.drop(columns=["temp", "humidity"])


def _apply_invalid_types(data: pd.DataFrame) -> pd.DataFrame:
    """Add invalid data types."""
    data.loc[0, "temp"] = "invalid"
    data.loc[1, "humidity"] = None
    return data


def _apply_extreme_values(data: pd.DataFrame) -> pd.DataFrame:
    """Add extreme but valid values."""
    data.loc[0, "temp"] = 100.0  # Very hot
    data.loc[1, "temp"] = -50.0  # Very cold
    data.loc[2, "wind_speed"] = 100.0  # Extreme wind
    return data


def _apply_null_values(data: pd.DataFrame) -> pd.DataFrame:
    """Add null values."""
    for col in ["temp", "humidity", "wind_speed"]:
        data.loc[data.sample(frac=0.1).index, col] = np.nan
    return data


def _apply_negative_values(data: pd.DataFrame) -> pd.DataFrame:
    """Add negative values where inappropriate."""
    data.loc[0, "demand"] = -10  # Negative demand
    return data


def _apply_large_values(data: pd.DataFrame) -> pd.DataFrame:
    """Add very large values."""
    data.loc[0, "demand"] = 1000000  # Very large demand
    return data


def _apply_duplicate_rows(data: pd.DataFrame) -> pd.DataFrame:
    """Add duplicates."""
    return pd.concat([data, data.iloc[0:5]], ignore_index=True)


@pytest.fixture
def edge_case_data(test_scenarios: str, sample_data: pd.DataFrame) -> pd.DataFrame:
    """Generate edge case data based on scenario."""
    data = sample_data.copy()

    # Map scenarios to handler functions
    scenario_handlers = {
        "missing_features": _apply_missing_features,
        "invalid_types": _apply_invalid_types,
        "extreme_values": _apply_extreme_values,
        "null_values": _apply_null_values,
        "negative_values": _apply_negative_values,
        "large_values": _apply_large_values,
        "duplicate_rows": _apply_duplicate_rows,
    }

    # Handle special cases that return early
    if test_scenarios == "empty_data":
        return pd.DataFrame(columns=data.columns)
    if test_scenarios == "single_row":
        return data.iloc[0:1]

    # Apply scenario-specific transformation
    if test_scenarios in scenario_handlers:
        data = scenario_handlers[test_scenarios](data)

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
