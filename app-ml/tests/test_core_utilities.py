#!/usr/bin/env python3
"""
Unit tests for core pipeline utilities

Tests for:
- validate_search_space_parameters()
- DatasetMonitor initialization
- DAG import smoke tests
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "dags"))

try:
    from demand_forecasting.utils.s3_helpers import validate_search_space_parameters

    S3_HELPERS_AVAILABLE = True
except ImportError:
    S3_HELPERS_AVAILABLE = False

try:
    from demand_forecasting.utils.dataset_monitor import DatasetMonitor

    DATASET_MONITOR_AVAILABLE = True
except ImportError:
    DATASET_MONITOR_AVAILABLE = False


class TestSearchSpaceValidation(unittest.TestCase):
    """Test validate_search_space_parameters function."""

    def setUp(self):
        if not S3_HELPERS_AVAILABLE:
            self.skipTest("s3_helpers not available")

    def test_valid_search_space(self):
        """Test validation with valid search space parameters."""
        valid_params = {
            "optuna": {
                "n_trials": 50,
                "search_space": {
                    "depth": {"min": 4, "max": 10},
                    "learning_rate": {"min": 0.01, "max": 0.3},
                    "iterations": {"min": 100, "max": 1000},
                },
            }
        }

        # Should not raise any exception
        try:
            validate_search_space_parameters(valid_params)
        except Exception as e:
            self.fail(f"Valid parameters raised exception: {e}")

    def test_missing_optuna_key(self):
        """Test validation fails when optuna key is missing."""
        invalid_params = {"other_key": "value"}

        with pytest.raises(KeyError) as context:
            validate_search_space_parameters(invalid_params)

        assert "optuna" in str(context.value)

    def test_missing_search_space(self):
        """Test validation fails when search_space is missing."""
        invalid_params = {
            "optuna": {
                "n_trials": 50,
                # Missing search_space
            }
        }

        with pytest.raises(KeyError) as context:
            validate_search_space_parameters(invalid_params)

        assert "search_space" in str(context.value)

    def test_invalid_parameter_ranges(self):
        """Test validation fails with invalid parameter ranges."""
        invalid_params = {
            "optuna": {
                "n_trials": 50,
                "search_space": {
                    "depth": {"min": 10, "max": 4},  # min > max
                    "learning_rate": {"min": 0.5, "max": 0.1},  # min > max
                },
            }
        }

        with pytest.raises(ValueError):
            validate_search_space_parameters(invalid_params)

    def test_empty_search_space(self):
        """Test validation fails with empty search space."""
        invalid_params = {"optuna": {"n_trials": 50, "search_space": {}}}

        with pytest.raises(ValueError):
            validate_search_space_parameters(invalid_params)


class TestDatasetMonitorInit(unittest.TestCase):
    """Test DatasetMonitor initialization."""

    def setUp(self):
        if not DATASET_MONITOR_AVAILABLE:
            self.skipTest("DatasetMonitor not available")
        import tempfile

        self._temp_dir = tempfile.TemporaryDirectory()
        self.metrics_dir = self._temp_dir.name

    def tearDown(self):
        if hasattr(self, "_temp_dir"):
            self._temp_dir.cleanup()

    @patch("demand_forecasting.utils.dataset_monitor.s3fs.S3FileSystem")
    def test_init_with_explicit_credentials(self, mock_s3fs):
        """Test initialization with explicit S3 credentials."""
        mock_fs = Mock()
        mock_s3fs.return_value = mock_fs

        monitor = DatasetMonitor(
            metrics_dir=self.metrics_dir,
            s3_endpoint="http://test:9000",
            s3_key="test_key",
            s3_secret="test_secret",
            s3_bucket="test-bucket",
        )

        # Verify S3 filesystem was initialized with correct credentials
        mock_s3fs.assert_called_once_with(
            client_kwargs={"endpoint_url": "http://test:9000"},
            key="test_key",
            secret="test_secret",
        )

        assert monitor.s3_endpoint == "http://test:9000"
        assert monitor.s3_key == "test_key"
        assert monitor.s3_secret == "test_secret"
        assert monitor.s3_bucket == "test-bucket"

    @patch("demand_forecasting.utils.dataset_monitor.s3fs.S3FileSystem")
    @patch.dict(
        os.environ, {"MINIO_ROOT_USER": "env_user", "MINIO_ROOT_PASSWORD": "env_pass"}
    )
    def test_init_with_env_credentials(self, mock_s3fs):
        """Test initialization falls back to environment credentials."""
        mock_fs = Mock()
        mock_s3fs.return_value = mock_fs

        monitor = DatasetMonitor(
            metrics_dir=self.metrics_dir,
            s3_endpoint="http://test:9000",
            s3_key=None,  # Should use env default
            s3_secret=None,  # Should use env default
            s3_bucket="test-bucket",
        )

        # Verify S3 filesystem was initialized with env credentials
        mock_s3fs.assert_called_once_with(
            client_kwargs={"endpoint_url": "http://test:9000"},
            key="env_user",
            secret="env_pass",
        )

        assert monitor.s3_key == "env_user"
        assert monitor.s3_secret == "env_pass"

    @patch("demand_forecasting.utils.dataset_monitor.s3fs.S3FileSystem")
    @patch.dict(os.environ, {}, clear=True)
    def test_init_with_default_credentials(self, mock_s3fs):
        """Test initialization avoids hardcoded credentials when env vars are unset."""
        mock_fs = Mock()
        mock_s3fs.return_value = mock_fs

        monitor = DatasetMonitor(
            metrics_dir=self.metrics_dir,
            s3_endpoint="http://test:9000",
            s3_key=None,
            s3_secret=None,
            s3_bucket="test-bucket",
        )

        mock_s3fs.assert_called_once_with(
            client_kwargs={"endpoint_url": "http://test:9000"},
            key=None,
            secret=None,
        )

        assert monitor.s3_key is None
        assert monitor.s3_secret is None

    @patch("demand_forecasting.utils.dataset_monitor.s3fs.S3FileSystem")
    def test_init_s3_failure_handling(self, mock_s3fs):
        """Test graceful handling of S3 initialization failure."""
        mock_s3fs.side_effect = Exception("S3 connection failed")

        monitor = DatasetMonitor(
            metrics_dir=self.metrics_dir,
            s3_endpoint="http://test:9000",
            s3_key="test_key",
            s3_secret="test_secret",
        )

        # Should handle S3 failure gracefully
        assert monitor.fs is None


class TestDAGImport(unittest.TestCase):
    """Test DAG import smoke tests."""

    def setUp(self):
        try:
            import airflow  # noqa: F401
        except ImportError:
            self.skipTest("apache-airflow not installed in unit test environment")

    def test_enhanced_dag_import(self):
        """Test that enhanced DAG can be imported without errors."""
        try:
            # This should not raise ImportError
            from airflow_dag_enhanced import demand_forecasting_dag

            # Verify DAG function exists and is callable
            assert callable(demand_forecasting_dag)

            # Test DAG creation (without Airflow context)
            try:
                dag = demand_forecasting_dag()
                assert dag is not None
                assert dag.dag_id == "demand_forecasting_enhanced"
            except Exception as e:
                # DAG creation might fail due to Airflow context, but import should work
                assert "airflow" in str(e).lower()

        except ImportError as e:
            self.fail(f"Enhanced DAG import failed: {e}")

    def test_dataset_monitoring_dag_import(self):
        """Test that dataset monitoring DAG can be imported."""
        try:
            from dataset_monitoring_dag import demand_forecasting_dag

            # Verify DAG function exists and is callable
            assert callable(demand_forecasting_dag)

        except ImportError as e:
            self.fail(f"Dataset monitoring DAG import failed: {e}")


class TestIntegrationSmoke(unittest.TestCase):
    """Integration smoke tests for core utilities."""

    def test_search_space_validation_integration(self):
        """Test search space validation with realistic parameters."""
        if not S3_HELPERS_AVAILABLE:
            self.skipTest("s3_helpers not available")

        # Test with realistic CatBoost parameters
        realistic_params = {
            "optuna": {
                "n_trials": 100,
                "timeout": 3600,
                "search_space": {
                    "depth": {"min": 4, "max": 10},
                    "learning_rate": {"min": 0.01, "max": 0.3, "log": True},
                    "iterations": {"min": 100, "max": 2000},
                    "l2_leaf_reg": {"min": 1, "max": 10},
                    "random_strength": {"min": 0.0, "max": 1.0},
                    "bagging_temperature": {"min": 0.0, "max": 1.0},
                    "border_count": {"min": 32, "max": 255},
                },
                "pruning": True,
                "sampler": "TPESampler",
            }
        }

        try:
            validate_search_space_parameters(realistic_params)
        except Exception as e:
            self.fail(f"Realistic parameters validation failed: {e}")

    @patch.dict(
        os.environ,
        {
            "MINIO_ROOT_USER": "test_user",
            "MINIO_ROOT_PASSWORD": "test_pass",
            "MINIO_ENDPOINT": "http://test:9000",
        },
    )
    @patch("demand_forecasting.utils.dataset_monitor.s3fs.S3FileSystem")
    def test_dataset_monitor_env_integration(self, mock_s3fs):
        """Test DatasetMonitor with environment configuration."""
        if not DATASET_MONITOR_AVAILABLE:
            self.skipTest("DatasetMonitor not available")

        mock_fs = Mock()
        mock_s3fs.return_value = mock_fs

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = DatasetMonitor(metrics_dir=tmpdir)

            # Should use environment variables
            assert monitor.s3_key == "test_user"
            assert monitor.s3_secret == "test_pass"
            assert monitor.s3_endpoint == "http://test:9000"


if __name__ == "__main__":
    # Configure test environment
    os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")

    # Run tests
    unittest.main(verbosity=2)
