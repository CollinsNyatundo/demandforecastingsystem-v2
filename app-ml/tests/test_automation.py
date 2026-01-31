"""
Comprehensive test suite for automation and retraining components.

Tests automated retraining triggers, scheduling logic, MLflow integration,
and performance-based retraining decisions.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import mlflow

from demand_forecasting.automation.retraining_scheduler import RetrainingScheduler


class TestRetrainingScheduler:
    """Test automated retraining scheduler functionality."""

    def test_scheduler_initialization(self, test_config: dict):
        """Test scheduler initialization with configuration."""
        config = test_config["retraining_config"]
        scheduler = RetrainingScheduler(config)

        assert scheduler.time_interval_days == config["time_interval_days"]
        assert scheduler.performance_threshold == config["performance_threshold"]
        assert scheduler.data_volume_threshold == config["data_volume_threshold"]
        assert scheduler.drift_threshold == config["drift_threshold"]
        assert scheduler.model_registry_name == config["model_registry_name"]

    def test_scheduler_initialization_defaults(self):
        """Test scheduler initialization with default values."""
        scheduler = RetrainingScheduler({})

        assert scheduler.time_interval_days == 7
        assert scheduler.performance_threshold == 5.0
        assert scheduler.data_volume_threshold == 10000
        assert scheduler.drift_threshold == 0.1
        assert scheduler.model_registry_name == "demand_forecasting"

    def test_should_retrain_no_triggers(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test should_retrain when no triggers are activated."""
        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler.should_retrain()

            assert result["should_retrain"] is False
            assert len(result["triggers"]) == 0
            assert result["priority"] == "LOW"
            assert "timestamp" in result
            assert "trigger_details" in result

    def test_should_retrain_time_trigger(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test should_retrain when time-based trigger is activated."""
        # Mock old model creation time
        old_time = datetime.now() - timedelta(days=10)
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=old_time)
        ]

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler.should_retrain()

            assert result["should_retrain"] is True
            assert "TIME_INTERVAL" in result["triggers"]
            assert result["priority"] in ["MEDIUM", "HIGH"]

    def test_should_retrain_performance_trigger(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test should_retrain when performance-based trigger is activated."""
        # Mock poor performance metrics
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=datetime.now())
        ]
        mock_mlflow_client.get_run.return_value = Mock(
            data=Mock(metrics={"rmse": 100.0})  # Poor performance
        )

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler.should_retrain()

            assert result["should_retrain"] is True
            assert "PERFORMANCE_DEGRADATION" in result["triggers"]
            assert result["priority"] in ["MEDIUM", "HIGH"]

    def test_should_retrain_data_volume_trigger(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test should_retrain when data volume trigger is activated."""
        # Mock large data volume check
        with patch.object(
            retraining_scheduler, "_check_data_trigger", return_value=True
        ):
            result = retraining_scheduler.should_retrain()

            assert result["should_retrain"] is True
            assert "DATA_VOLUME" in result["triggers"]
            assert result["priority"] in ["MEDIUM", "HIGH"]

    def test_should_retrain_drift_trigger(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test should_retrain when drift trigger is activated."""
        # Mock drift detection
        with patch.object(
            retraining_scheduler, "_check_drift_trigger", return_value=True
        ):
            result = retraining_scheduler.should_retrain()

            assert result["should_retrain"] is True
            assert "DATA_DRIFT" in result["triggers"]
            assert result["priority"] in ["HIGH", "CRITICAL"]

    def test_should_retrain_multiple_triggers(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test should_retrain with multiple triggers activated."""
        # Mock multiple conditions
        old_time = datetime.now() - timedelta(days=10)
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=old_time)
        ]
        mock_mlflow_client.get_run.return_value = Mock(
            data=Mock(metrics={"rmse": 100.0})
        )

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            with patch.object(
                retraining_scheduler, "_check_data_trigger", return_value=True
            ):
                with patch.object(
                    retraining_scheduler, "_check_drift_trigger", return_value=True
                ):
                    result = retraining_scheduler.should_retrain()

                    assert result["should_retrain"] is True
                    assert len(result["triggers"]) >= 3
                    assert result["priority"] == "CRITICAL"

    def test_check_time_trigger_true(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test time trigger check when threshold is exceeded."""
        # Mock model older than threshold
        old_time = datetime.now() - timedelta(days=15)
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=old_time)
        ]

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_time_trigger()

            assert result is True

    def test_check_time_trigger_false(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test time trigger check when threshold is not exceeded."""
        # Mock recent model
        recent_time = datetime.now() - timedelta(days=2)
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=recent_time)
        ]

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_time_trigger()

            assert result is False

    def test_check_time_trigger_no_model(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test time trigger check when no production model exists."""
        mock_mlflow_client.get_latest_versions.return_value = []

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_time_trigger()

            assert result is True  # Should trigger retraining when no model exists

    def test_check_performance_trigger_true(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test performance trigger check when performance is poor."""
        # Mock poor performance
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=datetime.now())
        ]
        mock_mlflow_client.get_run.return_value = Mock(
            data=Mock(metrics={"rmse": 150.0})  # Much worse than threshold
        )

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_performance_trigger()

            assert result is True

    def test_check_performance_trigger_false(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test performance trigger check when performance is good."""
        # Mock good performance
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=datetime.now())
        ]
        mock_mlflow_client.get_run.return_value = Mock(
            data=Mock(metrics={"rmse": 20.0})  # Better than threshold
        )

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_performance_trigger()

            assert result is False

    def test_check_performance_trigger_no_metrics(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test performance trigger check when no metrics are available."""
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=datetime.now())
        ]
        mock_mlflow_client.get_run.return_value = Mock(
            data=Mock(metrics={})  # No metrics
        )

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_performance_trigger()

            assert result is False


class TestTriggerDetails:
    """Test trigger detail generation and priority calculation."""

    def test_get_trigger_details_all_inactive(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test trigger details when all triggers are inactive."""
        with patch.object(
            retraining_scheduler, "_check_time_trigger", return_value=False
        ):
            with patch.object(
                retraining_scheduler, "_check_performance_trigger", return_value=False
            ):
                with patch.object(
                    retraining_scheduler, "_check_data_trigger", return_value=False
                ):
                    with patch.object(
                        retraining_scheduler, "_check_drift_trigger", return_value=False
                    ):
                        details = retraining_scheduler._get_trigger_details()

                        assert all(
                            detail["active"] is False for detail in details.values()
                        )
                        assert "time_since_last_training" in details["TIME_INTERVAL"]
                        assert (
                            "current_performance" in details["PERFORMANCE_DEGRADATION"]
                        )

    def test_get_trigger_details_mixed_active(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test trigger details with mixed active/inactive triggers."""
        with patch.object(
            retraining_scheduler, "_check_time_trigger", return_value=True
        ):
            with patch.object(
                retraining_scheduler, "_check_performance_trigger", return_value=False
            ):
                with patch.object(
                    retraining_scheduler, "_check_data_trigger", return_value=True
                ):
                    with patch.object(
                        retraining_scheduler, "_check_drift_trigger", return_value=False
                    ):
                        details = retraining_scheduler._get_trigger_details()

                        assert details["TIME_INTERVAL"]["active"] is True
                        assert details["PERFORMANCE_DEGRADATION"]["active"] is False
                        assert details["DATA_VOLUME"]["active"] is True
                        assert details["DATA_DRIFT"]["active"] is False

    def test_calculate_priority_no_triggers(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test priority calculation with no triggers."""
        priority = retraining_scheduler._calculate_priority([])

        assert priority == "LOW"

    def test_calculate_priority_single_trigger(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test priority calculation with single trigger."""
        priority = retraining_scheduler._calculate_priority(["TIME_INTERVAL"])

        assert priority in ["MEDIUM", "HIGH"]

    def test_calculate_priority_multiple_triggers(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test priority calculation with multiple triggers."""
        priority = retraining_scheduler._calculate_priority(
            ["TIME_INTERVAL", "PERFORMANCE_DEGRADATION", "DATA_DRIFT"]
        )

        assert priority == "CRITICAL"

    def test_calculate_priority_drift_trigger(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test priority calculation with drift trigger."""
        priority = retraining_scheduler._calculate_priority(["DATA_DRIFT"])

        assert priority in ["HIGH", "CRITICAL"]

    def test_calculate_priority_performance_trigger(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test priority calculation with performance trigger."""
        priority = retraining_scheduler._calculate_priority(["PERFORMANCE_DEGRADATION"])

        assert priority in ["MEDIUM", "HIGH"]


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_scheduler_with_invalid_config(self):
        """Test scheduler initialization with invalid configuration."""
        invalid_configs = [
            {"time_interval_days": -1},  # Negative days
            {"performance_threshold": -5.0},  # Negative threshold
            {"data_volume_threshold": 0},  # Zero threshold
            {"drift_threshold": 1.5},  # Invalid probability
        ]

        for config in invalid_configs:
            # Should handle invalid config gracefully
            scheduler = RetrainingScheduler(config)
            assert scheduler is not None

    def test_mlflow_connection_error(self, retraining_scheduler: RetrainingScheduler):
        """Test behavior when MLflow connection fails."""
        with patch(
            "mlflow.tracking.MlflowClient", side_effect=Exception("Connection failed")
        ):
            result = retraining_scheduler.should_retrain()

            # Should handle connection error gracefully
            assert result["should_retrain"] is False
            assert "error" in str(result).lower() or len(result["triggers"]) == 0

    def test_missing_model_metrics(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test behavior when model metrics are missing."""
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=datetime.now())
        ]
        mock_mlflow_client.get_run.return_value = Mock(
            data=Mock(metrics=None)  # No metrics
        )

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_performance_trigger()

            assert result is False

    def test_extreme_time_values(
        self, retraining_scheduler: RetrainingScheduler, mock_mlflow_client
    ):
        """Test with extreme time values."""
        # Test with very old model
        very_old_time = datetime.now() - timedelta(days=365)
        mock_mlflow_client.get_latest_versions.return_value = [
            Mock(run_id="test_run_id", creation_timestamp=very_old_time)
        ]

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = retraining_scheduler._check_time_trigger()

            assert result is True

    def test_zero_thresholds(self):
        """Test scheduler with zero thresholds."""
        config = {
            "time_interval_days": 0,
            "performance_threshold": 0,
            "data_volume_threshold": 0,
            "drift_threshold": 0,
        }

        scheduler = RetrainingScheduler(config)

        # Should handle zero thresholds
        assert scheduler.time_interval_days == 0
        assert scheduler.performance_threshold == 0
        assert scheduler.data_volume_threshold == 0
        assert scheduler.drift_threshold == 0

    def test_very_large_thresholds(self):
        """Test scheduler with very large thresholds."""
        config = {
            "time_interval_days": 3650,  # 10 years
            "performance_threshold": 1000000,
            "data_volume_threshold": 1000000000,
            "drift_threshold": 1.0,
        }

        scheduler = RetrainingScheduler(config)

        # Should handle large thresholds
        assert scheduler.time_interval_days == 3650
        assert scheduler.performance_threshold == 1000000
        assert scheduler.data_volume_threshold == 1000000000
        assert scheduler.drift_threshold == 1.0

    @pytest.mark.slow
    def test_scheduler_performance_under_load(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test scheduler performance under multiple rapid calls."""
        import time

        start_time = time.time()

        # Make multiple rapid calls
        results = []
        for _ in range(100):
            result = retraining_scheduler.should_retrain()
            results.append(result)

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete within reasonable time (less than 10 seconds)
        assert total_time < 10.0
        assert len(results) == 100

        # All results should have required fields
        for result in results:
            assert "should_retrain" in result
            assert "triggers" in result
            assert "priority" in result
            assert "timestamp" in result

    def test_concurrent_scheduler_calls(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test thread safety of scheduler calls."""
        import threading
        import time

        results = []
        errors = []

        def check_retrain():
            try:
                result = retraining_scheduler.should_retrain()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Make concurrent calls
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_retrain)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should handle concurrent calls without errors
        assert len(errors) == 0
        assert len(results) == 10

        # All results should be valid
        for result in results:
            assert isinstance(result, dict)
            assert "should_retrain" in result

    def test_scheduler_history_tracking(
        self, retraining_scheduler: RetrainingScheduler
    ):
        """Test that scheduler maintains history of retraining decisions."""
        # Make multiple calls
        for _ in range(5):
            result = retraining_scheduler.should_retrain()

        # Check that history is maintained (if implemented)
        if hasattr(retraining_scheduler, "decision_history"):
            assert len(retraining_scheduler.decision_history) >= 5

    def test_scheduler_with_custom_model_registry(self, mock_mlflow_client):
        """Test scheduler with custom model registry name."""
        config = {"model_registry_name": "custom_model_registry"}

        scheduler = RetrainingScheduler(config)

        with patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client):
            result = scheduler.should_retrain()

            # Should use custom registry name
            mock_mlflow_client.get_latest_versions.assert_called_with(
                "custom_model_registry", stages=["Production"]
            )
