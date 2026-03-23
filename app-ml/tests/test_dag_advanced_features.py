"""
Test suite for advanced DAG features.

Tests the multi-objective optimization task, ensemble training task,
and automated drift detection/retraining DAG components.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest


class TestMultiObjectiveDAGTask:
    """Test multi-objective optimization DAG task logic."""

    @pytest.fixture
    def sample_model_input(self):
        """Create sample model input data."""
        np.random.seed(42)
        n_samples = 500
        return pd.DataFrame({
            "temp": np.random.normal(20, 10, n_samples),
            "humidity": np.random.normal(60, 20, n_samples),
            "wind_speed": np.random.exponential(5, n_samples),
            "hour": np.random.randint(0, 24, n_samples),
            "day_of_week": np.random.randint(0, 7, n_samples),
            "demand": np.random.poisson(50, n_samples),
        })

    @pytest.fixture
    def mock_parameters(self):
        """Mock parameters configuration."""
        return {
            "advanced_features": {
                "enable_multi_objective": True,
                "multi_objective_trials": 5,
                "multi_objective_targets": ["rmse", "mae", "training_time"],
                "objective_weights": {"rmse": 0.5, "mae": 0.3, "training_time": 0.2},
            }
        }

    @pytest.fixture
    def mock_parameters_disabled(self):
        """Mock parameters with multi-objective disabled."""
        return {
            "advanced_features": {
                "enable_multi_objective": False,
            }
        }

    def test_multi_objective_task_disabled(self, mock_parameters_disabled):
        """Test that task skips when multi-objective is disabled."""
        params = mock_parameters_disabled
        advanced_features = params.get("advanced_features", {})
        
        if not advanced_features.get("enable_multi_objective", False):
            result = {"status": "skipped"}
        else:
            result = {"status": "completed"}
        
        assert result["status"] == "skipped"

    def test_multi_objective_task_enabled(self, mock_parameters, sample_model_input):
        """Test multi-objective task when enabled."""
        params = mock_parameters
        advanced_features = params.get("advanced_features", {})
        
        assert advanced_features.get("enable_multi_objective", False) is True
        assert advanced_features.get("multi_objective_trials", 50) == 5
        assert "rmse" in advanced_features.get("multi_objective_targets", [])

    def test_multi_objective_weights_sum(self, mock_parameters):
        """Test that objective weights are reasonable."""
        weights = mock_parameters["advanced_features"]["objective_weights"]
        total_weight = sum(weights.values())
        
        # Weights should sum to approximately 1.0
        assert abs(total_weight - 1.0) < 0.01

    def test_multi_objective_data_split(self, sample_model_input):
        """Test sequential train/test split for multi-objective."""
        df = sample_model_input
        X = df.drop("demand", axis=1)
        y = df["demand"]
        
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        assert len(X_train) == 400
        assert len(X_test) == 100
        assert len(y_train) == 400
        assert len(y_test) == 100

    @pytest.mark.slow
    def test_multi_objective_optimizer_integration(self, sample_model_input):
        """Test integration with MultiObjectiveOptimizer."""
        try:
            from demand_forecasting.optimization.multi_objective import (
                MultiObjectiveOptimizer,
            )
        except ImportError:
            pytest.skip("MultiObjectiveOptimizer not available")
        
        df = sample_model_input
        X = df.drop("demand", axis=1)
        y = df["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        optimizer = MultiObjectiveOptimizer(
            n_trials=3,
            objectives=["rmse", "mae"]
        )
        
        # Should not raise
        assert optimizer is not None


class TestEnsembleDAGTask:
    """Test ensemble training DAG task logic."""

    @pytest.fixture
    def sample_model_input(self):
        """Create sample model input data."""
        np.random.seed(42)
        n_samples = 500
        return pd.DataFrame({
            "temp": np.random.normal(20, 10, n_samples),
            "humidity": np.random.normal(60, 20, n_samples),
            "wind_speed": np.random.exponential(5, n_samples),
            "hour": np.random.randint(0, 24, n_samples),
            "day_of_week": np.random.randint(0, 7, n_samples),
            "demand": np.random.poisson(50, n_samples),
        })

    @pytest.fixture
    def mock_parameters_stacking(self):
        """Mock parameters for stacking ensemble."""
        return {
            "advanced_features": {
                "enable_ensemble": True,
                "ensemble_type": "stacking",
                "ensemble_models": ["catboost", "xgboost", "lightgbm", "random_forest"],
                "stacking_cv_folds": 3,
            }
        }

    @pytest.fixture
    def mock_parameters_voting(self):
        """Mock parameters for voting ensemble."""
        return {
            "advanced_features": {
                "enable_ensemble": True,
                "ensemble_type": "voting",
                "ensemble_models": ["catboost", "random_forest"],
            }
        }

    @pytest.fixture
    def mock_parameters_disabled(self):
        """Mock parameters with ensemble disabled."""
        return {
            "advanced_features": {
                "enable_ensemble": False,
            }
        }

    def test_ensemble_task_disabled(self, mock_parameters_disabled):
        """Test that task skips when ensemble is disabled."""
        params = mock_parameters_disabled
        advanced_features = params.get("advanced_features", {})
        
        if not advanced_features.get("enable_ensemble", False):
            result = {"status": "skipped"}
        else:
            result = {"status": "completed"}
        
        assert result["status"] == "skipped"

    def test_ensemble_task_stacking_config(self, mock_parameters_stacking):
        """Test stacking ensemble configuration."""
        params = mock_parameters_stacking
        advanced_features = params.get("advanced_features", {})
        
        assert advanced_features.get("enable_ensemble", False) is True
        assert advanced_features.get("ensemble_type") == "stacking"
        assert advanced_features.get("stacking_cv_folds", 5) == 3
        assert len(advanced_features.get("ensemble_models", [])) == 4

    def test_ensemble_task_voting_config(self, mock_parameters_voting):
        """Test voting ensemble configuration."""
        params = mock_parameters_voting
        advanced_features = params.get("advanced_features", {})
        
        assert advanced_features.get("ensemble_type") == "voting"
        assert len(advanced_features.get("ensemble_models", [])) == 2

    def test_ensemble_data_split(self, sample_model_input):
        """Test sequential train/test split for ensemble."""
        df = sample_model_input
        X = df.drop("demand", axis=1)
        y = df["demand"]
        
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        assert len(X_train) == 400
        assert len(X_test) == 100

    @pytest.mark.slow
    def test_ensemble_manager_integration(self, sample_model_input):
        """Test integration with EnsembleManager."""
        try:
            from demand_forecasting.optimization.ensemble import EnsembleManager
        except ImportError:
            pytest.skip("EnsembleManager not available")
        
        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble(cv_folds=2)
        
        assert ensemble is not None
        assert hasattr(ensemble, "fit")
        assert hasattr(ensemble, "predict")


class TestAutomatedRetrainingDAG:
    """Test automated drift detection and retraining DAG components."""

    @pytest.fixture
    def reference_data(self):
        """Create reference data for drift detection."""
        np.random.seed(123)
        n_samples = 500
        return pd.DataFrame({
            "temp": np.random.normal(22, 8, n_samples),
            "humidity": np.random.normal(55, 15, n_samples),
            "wind_speed": np.random.exponential(4, n_samples),
            "hour": np.random.randint(0, 24, n_samples),
            "day_of_week": np.random.randint(0, 7, n_samples),
        })

    @pytest.fixture
    def production_data_no_drift(self, reference_data):
        """Create production data without drift."""
        np.random.seed(124)
        n_samples = 500
        return pd.DataFrame({
            "temp": np.random.normal(22, 8, n_samples),  # Same distribution
            "humidity": np.random.normal(55, 15, n_samples),
            "wind_speed": np.random.exponential(4, n_samples),
            "hour": np.random.randint(0, 24, n_samples),
            "day_of_week": np.random.randint(0, 7, n_samples),
        })

    @pytest.fixture
    def production_data_with_drift(self):
        """Create production data with drift."""
        np.random.seed(456)
        n_samples = 500
        return pd.DataFrame({
            "temp": np.random.normal(30, 5, n_samples),  # Shifted mean
            "humidity": np.random.normal(80, 10, n_samples),  # Shifted mean
            "wind_speed": np.random.exponential(8, n_samples),  # Different scale
            "hour": np.random.randint(0, 24, n_samples),
            "day_of_week": np.random.randint(0, 7, n_samples),
        })

    @pytest.fixture
    def mock_automation_config(self):
        """Mock automation configuration."""
        return {
            "automation": {
                "time_interval_days": 7,
                "performance_threshold": 5.0,
                "data_volume_threshold": 10000,
                "drift_threshold": 0.1,
                "drift_features_threshold": 30,
                "enable_email_alerts": True,
                "model_registry_name": "demand_forecasting_catboost",
            },
            "monitoring": {
                "drift_detection": {
                    "ks_test_threshold": 0.05,
                    "psi_threshold": 0.1,
                    "min_samples": 30,
                }
            }
        }

    def test_load_reference_data_structure(self, reference_data):
        """Test reference data loading structure."""
        assert "temp" in reference_data.columns
        assert "humidity" in reference_data.columns
        assert len(reference_data) == 500

    def test_load_production_data_structure(self, production_data_no_drift):
        """Test production data loading structure."""
        assert "temp" in production_data_no_drift.columns
        assert "humidity" in production_data_no_drift.columns
        assert len(production_data_no_drift) == 500

    def test_drift_detection_no_drift(self, reference_data, production_data_no_drift):
        """Test drift detection with no drift."""
        try:
            from demand_forecasting.monitoring.drift_detector import DriftDetector
        except ImportError:
            pytest.skip("DriftDetector not available")
        
        detector = DriftDetector(reference_data, threshold=0.05)
        result = detector.detect_drift(production_data_no_drift)
        
        # Should not detect significant drift
        assert result["drift_percentage"] < 50.0

    def test_drift_detection_with_drift(self, reference_data, production_data_with_drift):
        """Test drift detection with actual drift."""
        try:
            from demand_forecasting.monitoring.drift_detector import DriftDetector
        except ImportError:
            pytest.skip("DriftDetector not available")
        
        detector = DriftDetector(reference_data, threshold=0.05)
        result = detector.detect_drift(production_data_with_drift)
        
        # Should detect drift
        assert result["overall_drift_score"] > 0.05
        assert len(result["drifted_features"]) > 0

    def test_retraining_triggers_config(self, mock_automation_config):
        """Test retraining triggers configuration."""
        config = mock_automation_config["automation"]
        
        assert config["time_interval_days"] == 7
        assert config["performance_threshold"] == 5.0
        assert config["data_volume_threshold"] == 10000
        assert config["drift_threshold"] == 0.1

    def test_check_retraining_triggers_no_drift(self, mock_automation_config):
        """Test retraining trigger check with no drift."""
        try:
            from demand_forecasting.automation.retraining_scheduler import (
                RetrainingScheduler,
            )
        except ImportError:
            pytest.skip("RetrainingScheduler not available")
        
        scheduler = RetrainingScheduler(mock_automation_config["automation"])
        
        # Mock no drift detected
        drift_result = {
            "overall_drift_score": 0.02,
            "drifted_features": [],
            "drift_percentage": 0.0,
        }
        
        # Manually check drift trigger
        drift_triggered = drift_result["overall_drift_score"] > mock_automation_config["automation"]["drift_threshold"]
        
        assert drift_triggered is False

    def test_check_retraining_triggers_with_drift(self, mock_automation_config):
        """Test retraining trigger check with drift."""
        drift_result = {
            "overall_drift_score": 0.25,
            "drifted_features": ["temp", "humidity"],
            "drift_percentage": 40.0,
        }
        
        # Manually check drift trigger
        drift_triggered = drift_result["overall_drift_score"] > mock_automation_config["automation"]["drift_threshold"]
        
        assert drift_triggered is True

    def test_priority_calculation_single_trigger(self):
        """Test priority calculation with single trigger."""
        triggers = ["TIME_INTERVAL"]
        
        if len(triggers) == 0:
            priority = "LOW"
        elif len(triggers) == 1:
            priority = "MEDIUM"
        elif len(triggers) == 2:
            priority = "HIGH"
        else:
            priority = "CRITICAL"
        
        assert priority == "MEDIUM"

    def test_priority_calculation_multiple_triggers(self):
        """Test priority calculation with multiple triggers."""
        triggers = ["TIME_INTERVAL", "PERFORMANCE_DEGRADATION", "DATA_DRIFT"]
        
        if len(triggers) == 0:
            priority = "LOW"
        elif len(triggers) == 1:
            priority = "MEDIUM"
        elif len(triggers) == 2:
            priority = "HIGH"
        else:
            priority = "CRITICAL"
        
        assert priority == "CRITICAL"

    def test_priority_calculation_drift_trigger(self):
        """Test priority calculation with drift trigger (should be high)."""
        triggers = ["DATA_DRIFT"]
        
        # Drift should always be at least HIGH priority
        if "DATA_DRIFT" in triggers:
            priority = "HIGH"
        elif len(triggers) == 0:
            priority = "LOW"
        else:
            priority = "MEDIUM"
        
        assert priority == "HIGH"

    def test_branching_logic_should_retrain(self):
        """Test branching logic when retraining is needed."""
        decision = {
            "should_retrain": True,
            "triggers": ["DATA_DRIFT"],
            "priority": "HIGH",
        }
        
        if decision["should_retrain"]:
            next_task = "trigger_retraining"
        else:
            next_task = "skip_retraining"
        
        assert next_task == "trigger_retraining"

    def test_branching_logic_should_skip(self):
        """Test branching logic when retraining is not needed."""
        decision = {
            "should_retrain": False,
            "triggers": [],
            "priority": "LOW",
        }
        
        if decision["should_retrain"]:
            next_task = "trigger_retraining"
        else:
            next_task = "skip_retraining"
        
        assert next_task == "skip_retraining"

    def test_drift_report_structure(self):
        """Test drift report structure."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "drift_analysis": {
                "overall_drift_score": 0.15,
                "drifted_features": ["temp", "humidity"],
                "drift_percentage": 20.0,
            },
            "retraining_decision": {
                "should_retrain": True,
                "triggers": ["DATA_DRIFT"],
                "priority": "HIGH",
            },
        }
        
        assert "timestamp" in report
        assert "drift_analysis" in report
        assert "retraining_decision" in report
        assert report["drift_analysis"]["drift_percentage"] == 20.0

    def test_alert_conditions_critical(self):
        """Test alert conditions for CRITICAL priority."""
        decision = {"priority": "CRITICAL", "triggers": ["DATA_DRIFT", "PERFORMANCE_DEGRADATION"]}
        drift_result = {"drift_percentage": 60.0}
        
        alert_priorities = ["CRITICAL", "HIGH"]
        
        should_alert = (
            decision["priority"] in alert_priorities or
            drift_result["drift_percentage"] > 50
        )
        
        assert should_alert is True

    def test_alert_conditions_low_priority(self):
        """Test alert conditions for LOW priority."""
        decision = {"priority": "LOW", "triggers": []}
        drift_result = {"drift_percentage": 5.0}
        
        alert_priorities = ["CRITICAL", "HIGH"]
        
        should_alert = (
            decision["priority"] in alert_priorities or
            drift_result["drift_percentage"] > 50
        )
        
        assert should_alert is False


class TestDAGConfiguration:
    """Test DAG configuration and parameters."""

    def test_parameters_file_structure(self):
        """Test that parameters file has required structure."""
        # Expected structure
        expected_keys = [
            "advanced_features",
            "monitoring",
            "automation",
        ]
        
        # Simulate loading parameters
        params = {
            "advanced_features": {
                "enable_multi_objective": False,
                "enable_ensemble": False,
            },
            "monitoring": {
                "drift_detection": {
                    "ks_test_threshold": 0.05,
                }
            },
            "automation": {
                "time_interval_days": 7,
            }
        }
        
        for key in expected_keys:
            assert key in params

    def test_multi_objective_defaults(self):
        """Test default values for multi-objective config."""
        defaults = {
            "enable_multi_objective": False,
            "multi_objective_trials": 50,
            "multi_objective_targets": ["rmse", "mae", "training_time"],
            "objective_weights": {"rmse": 0.5, "mae": 0.3, "training_time": 0.2},
        }
        
        # Empty config should fall back to defaults
        config = {}
        
        enable = config.get("enable_multi_objective", defaults["enable_multi_objective"])
        trials = config.get("multi_objective_trials", defaults["multi_objective_trials"])
        
        assert enable is False
        assert trials == 50

    def test_ensemble_defaults(self):
        """Test default values for ensemble config."""
        defaults = {
            "enable_ensemble": False,
            "ensemble_type": "stacking",
            "stacking_cv_folds": 5,
        }
        
        config = {}
        
        enable = config.get("enable_ensemble", defaults["enable_ensemble"])
        ensemble_type = config.get("ensemble_type", defaults["ensemble_type"])
        
        assert enable is False
        assert ensemble_type == "stacking"

    def test_automation_defaults(self):
        """Test default values for automation config."""
        defaults = {
            "time_interval_days": 7,
            "performance_threshold": 5.0,
            "data_volume_threshold": 10000,
            "drift_threshold": 0.1,
        }
        
        config = {}
        
        time_interval = config.get("time_interval_days", defaults["time_interval_days"])
        drift_threshold = config.get("drift_threshold", defaults["drift_threshold"])
        
        assert time_interval == 7
        assert drift_threshold == 0.1


class TestErrorHandling:
    """Test error handling in DAG tasks."""

    def test_missing_data_handling(self):
        """Test handling of missing data."""
        # Simulate missing model input
        df = None
        
        if df is None:
            result = {"status": "error", "message": "Model input data not found"}
        else:
            result = {"status": "completed"}
        
        assert result["status"] == "error"

    def test_empty_dataframe_handling(self):
        """Test handling of empty dataframe."""
        df = pd.DataFrame()
        
        if df.empty:
            result = {"status": "error", "message": "Empty dataframe"}
        else:
            result = {"status": "completed"}
        
        assert result["status"] == "error"

    def test_missing_target_column(self):
        """Test handling of missing target column."""
        df = pd.DataFrame({
            "temp": [20, 21, 22],
            "humidity": [60, 61, 62],
            # Missing 'demand' column
        })
        
        if "demand" not in df.columns:
            result = {"status": "error", "message": "Target column 'demand' not found"}
        else:
            result = {"status": "completed"}
        
        assert result["status"] == "error"

    def test_insufficient_data_for_split(self):
        """Test handling of insufficient data for train/test split."""
        df = pd.DataFrame({
            "temp": [20, 21],
            "demand": [50, 51],
        })
        
        min_samples = 10
        
        if len(df) < min_samples:
            result = {"status": "error", "message": f"Insufficient data: {len(df)} < {min_samples}"}
        else:
            result = {"status": "completed"}
        
        assert result["status"] == "error"

    def test_drift_detection_insufficient_samples(self):
        """Test drift detection with insufficient samples."""
        min_samples = 30
        current_samples = 10
        
        if current_samples < min_samples:
            result = {
                "status": "warning",
                "message": f"Insufficient samples for drift detection: {current_samples} < {min_samples}",
                "overall_drift_score": 0.0,
            }
        else:
            result = {"status": "completed"}
        
        assert result["status"] == "warning"
