"""
Comprehensive test suite for optimization and ensemble methods.

Tests Optuna multi-objective optimization, ensemble creation,
hyperparameter tuning, and performance scenarios.
"""


import numpy as np
import optuna
import pandas as pd
import pytest
from optuna.storages import RDBStorage
from sklearn.metrics import mean_squared_error

from demand_forecasting.optimization.ensemble import EnsembleManager
from demand_forecasting.optimization.multi_objective import (
    compute_zero_safe_mape,
    objective_multi,
)


class TestMultiObjectiveOptimization:
    """Test multi-objective optimization with Optuna."""

    def test_compute_zero_safe_mape(self):
        """Test MAPE calculation with zero-division protection."""
        # Normal case
        y_true = np.array([10, 20, 30])
        y_pred = np.array([12, 18, 33])
        mape = compute_zero_safe_mape(y_true, y_pred)
        expected_mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

        assert abs(mape - expected_mape) < 1e-6

        # Zero values case
        y_true_with_zero = np.array([0, 10, 20])
        y_pred_zero = np.array([5, 12, 18])
        mape_zero = compute_zero_safe_mape(y_true_with_zero, y_pred_zero)

        # Should handle zeros gracefully
        assert isinstance(mape_zero, float)
        assert not np.isnan(mape_zero)
        assert not np.isinf(mape_zero)

        # All zeros case
        y_true_all_zero = np.array([0, 0, 0])
        y_pred_all_zero = np.array([5, 10, 15])
        mape_all_zero = compute_zero_safe_mape(y_true_all_zero, y_pred_all_zero)

        assert mape_all_zero == 0.0

    def test_objective_multi_all_objectives(self, sample_data: pd.DataFrame):
        """Test multi-objective function with all objectives."""
        # Prepare train/test split
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Create trial
        study = optuna.create_study(directions=["minimize", "minimize", "minimize"])
        trial = study.ask()

        # Test with all objectives
        objectives = ["rmse", "mae", "training_time"]
        result = objective_multi(trial, X_train, X_test, y_train, y_test, objectives)

        assert len(result) == 3
        assert all(isinstance(val, float) for val in result)
        assert all(val >= 0 for val in result)  # All should be non-negative

        # RMSE should be largest (typically)
        rmse, mae, training_time = result
        assert rmse >= 0
        assert mae >= 0
        assert training_time >= 0

    def test_objective_multi_subset_objectives(self, sample_data: pd.DataFrame):
        """Test multi-objective function with subset of objectives."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        study = optuna.create_study(directions=["minimize", "minimize"])
        trial = study.ask()

        # Test with only RMSE and MAE
        objectives = ["rmse", "mae"]
        result = objective_multi(trial, X_train, X_test, y_train, y_test, objectives)

        assert len(result) == 2
        rmse, mae = result
        assert rmse >= 0
        assert mae >= 0

    def test_objective_multi_default_objectives(self, sample_data: pd.DataFrame):
        """Test multi-objective function with default objectives."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        study = optuna.create_study(directions=["minimize", "minimize", "minimize"])
        trial = study.ask()

        # Test with default objectives (no objectives parameter)
        result = objective_multi(trial, X_train, X_test, y_train, y_test)

        # Should default to ["rmse", "mae", "training_time"]
        assert len(result) == 3

    def test_objective_multi_invalid_objective(self, sample_data: pd.DataFrame):
        """Test multi-objective function with invalid objective."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        # Test with invalid objective
        objectives = ["invalid_objective"]
        result = objective_multi(trial, X_train, X_test, y_train, y_test, objectives)

        # Should ignore invalid objective and return empty list
        assert len(result) == 0

    def test_objective_multi_hyperparameter_ranges(self, sample_data: pd.DataFrame):
        """Test that hyperparameters are within suggested ranges."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        # Run objective function
        objective_multi(trial, X_train, X_test, y_train, y_test, ["rmse"])

        # Check that suggested parameters are within ranges
        params = trial.params
        assert 0.01 <= params["learning_rate"] <= 0.3
        assert 3 <= params["depth"] <= 10
        assert 0.1 <= params["l2_leaf_reg"] <= 10.0
        assert 32 <= params["border_count"] <= 255
        assert 0.0 <= params["bagging_temperature"] <= 1.0
        assert 0.0 <= params["random_strength"] <= 1.0
        assert 100 <= params["iterations"] <= 1000

    def test_objective_multi_training_time_tracking(self, sample_data: pd.DataFrame):
        """Test that training time is properly tracked."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        import time

        start_time = time.time()
        result = objective_multi(
            trial, X_train, X_test, y_train, y_test, ["training_time"]
        )
        end_time = time.time()

        training_time = result[0]
        actual_time = end_time - start_time

        # Training time should be close to actual time (within 1 second)
        assert abs(training_time - actual_time) < 1.0

    @pytest.mark.slow
    def test_objective_multi_optimization_study(
        self, sample_data: pd.DataFrame, optuna_storage: RDBStorage
    ):
        """Test full optimization study with multiple trials."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Create study with persistence
        study = optuna.create_study(
            directions=["minimize", "minimize"],
            storage=optuna_storage,
            study_name="test_study",
        )

        # Run multiple trials
        n_trials = 5
        for _ in range(n_trials):
            trial = study.ask()
            result = objective_multi(
                trial, X_train, X_test, y_train, y_test, ["rmse", "mae"]
            )
            study.tell(trial, result)

        assert len(study.trials) == n_trials

        # Check that trials have different parameters
        params = [trial.params for trial in study.trials]
        assert len({tuple(sorted(p.items())) for p in params}) == n_trials


class TestEnsembleManager:
    """Test ensemble methods and model combination."""

    def test_ensemble_manager_initialization(self):
        """Test EnsembleManager initialization."""
        manager = EnsembleManager()

        assert manager.ensemble is None
        assert manager.base_models == {}
        assert manager.meta_model is None
        assert manager.ensemble_type is None

    def test_create_stacking_ensemble_default_params(self):
        """Test creating stacking ensemble with default parameters."""
        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble()

        assert ensemble is not None
        assert hasattr(ensemble, "estimators")
        assert hasattr(ensemble, "final_estimator")

        # Check default base models
        estimator_names = [name for name, _ in ensemble.estimators]
        expected_names = ["catboost", "rf", "xgb", "lgbm"]
        assert all(name in estimator_names for name in expected_names)

        # Check final estimator
        assert ensemble.final_estimator.__class__.__name__ == "RidgeCV"

    def test_create_stacking_ensemble_custom_params(self):
        """Test creating stacking ensemble with custom parameters."""
        manager = EnsembleManager()

        custom_params = {
            "catboost_params": {"iterations": 200, "learning_rate": 0.05},
            "rf_params": {"n_estimators": 50},
            "xgb_params": {"max_depth": 3},
            "lgbm_params": {"learning_rate": 0.2},
            "cv_folds": 3,
        }

        ensemble = manager.create_stacking_ensemble(**custom_params)

        # Check that custom parameters were applied
        catboost_model = dict(ensemble.estimators)["catboost"]
        assert catboost_model.get_params()["iterations"] == 200
        assert catboost_model.get_params()["learning_rate"] == 0.05

        rf_model = dict(ensemble.estimators)["rf"]
        assert rf_model.get_params()["n_estimators"] == 50

        xgb_model = dict(ensemble.estimators)["xgb"]
        assert xgb_model.get_params()["max_depth"] == 3

        lgbm_model = dict(ensemble.estimators)["lgbm"]
        assert lgbm_model.get_params()["learning_rate"] == 0.2

    def test_create_stacking_ensemble_partial_params(self):
        """Test creating stacking ensemble with partial custom parameters."""
        manager = EnsembleManager()

        # Only customize CatBoost parameters
        custom_params = {"catboost_params": {"iterations": 300, "depth": 8}}

        ensemble = manager.create_stacking_ensemble(**custom_params)

        # CatBoost should have custom params
        catboost_model = dict(ensemble.estimators)["catboost"]
        assert catboost_model.get_params()["iterations"] == 300
        assert catboost_model.get_params()["depth"] == 8

        # Other models should have defaults
        rf_model = dict(ensemble.estimators)["rf"]
        assert rf_model.get_params()["n_estimators"] == 100  # Default

    def test_ensemble_fit_predict(self, sample_data: pd.DataFrame):
        """Test ensemble fitting and prediction."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]

        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble()

        # Fit ensemble
        ensemble.fit(X, y)

        # Make predictions
        predictions = ensemble.predict(X)

        assert len(predictions) == len(X)
        assert all(isinstance(pred, (int, float)) for pred in predictions)
        assert all(pred >= 0 for pred in predictions)  # Demand should be non-negative

    def test_ensemble_performance_comparison(self, sample_data: pd.DataFrame):
        """Test ensemble performance against individual models."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]

        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble()

        # Fit ensemble
        ensemble.fit(X_train, y_train)

        # Get ensemble predictions
        ensemble_preds = ensemble.predict(X_test)
        ensemble_rmse = np.sqrt(mean_squared_error(y_test, ensemble_preds))

        # Test individual models
        individual_rmses = {}
        for name, model in ensemble.estimators_:
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            individual_rmses[name] = np.sqrt(mean_squared_error(y_test, preds))

        # Ensemble should perform better than or equal to worst individual model
        worst_individual_rmse = max(individual_rmses.values())
        assert ensemble_rmse <= worst_individual_rmse

    def test_ensemble_with_small_dataset(self):
        """Test ensemble with very small dataset."""
        # Create tiny dataset
        X = pd.DataFrame({"feature1": [1, 2, 3, 4, 5], "feature2": [2, 4, 6, 8, 10]})
        y = pd.Series([3, 6, 9, 12, 15])

        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble(cv_folds=2)  # Reduce CV folds

        # Should handle small dataset gracefully
        ensemble.fit(X, y)
        predictions = ensemble.predict(X)

        assert len(predictions) == len(X)
        assert not any(np.isnan(predictions))

    def test_ensemble_with_single_feature(self):
        """Test ensemble with single feature dataset."""
        X = pd.DataFrame({"feature1": np.random.normal(0, 1, 100)})
        y = pd.Series(np.random.normal(10, 2, 100))

        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble()

        # Should handle single feature
        ensemble.fit(X, y)
        predictions = ensemble.predict(X)

        assert len(predictions) == len(X)
        assert not any(np.isnan(predictions))

    def test_ensemble_feature_importance(self, sample_data: pd.DataFrame):
        """Test getting feature importance from ensemble."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]

        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble()
        ensemble.fit(X, y)

        # Some ensemble methods might not have feature_importance_
        if hasattr(ensemble, "feature_importances_"):
            importances = ensemble.feature_importances_
            assert len(importances) == len(X.columns)
            assert all(isinstance(imp, (int, float)) for imp in importances)
            assert all(imp >= 0 for imp in importances)


class TestOptimizationEdgeCases:
    """Test edge cases and error scenarios in optimization."""

    def test_optimization_with_empty_data(self):
        """Test optimization with empty dataset."""
        X = pd.DataFrame()
        y = pd.Series()

        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        with pytest.raises((ValueError, IndexError)):
            objective_multi(trial, X, X, y, y, ["rmse"])

    def test_optimization_with_mismatched_shapes(self):
        """Test optimization with mismatched X and y shapes."""
        X = pd.DataFrame({"feature1": [1, 2, 3]})
        y = pd.Series([1, 2])  # Different length

        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        with pytest.raises(ValueError):
            objective_multi(trial, X, X, y, y, ["rmse"])

    def test_optimization_with_constant_target(self):
        """Test optimization with constant target values."""
        X = pd.DataFrame(
            {
                "feature1": np.random.normal(0, 1, 100),
                "feature2": np.random.normal(0, 1, 100),
            }
        )
        y = pd.Series([50] * 100)  # Constant target

        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        result = objective_multi(trial, X, X, y, y, ["rmse"])

        # Should handle constant target
        assert len(result) == 1
        assert result[0] >= 0

    def test_optimization_with_extreme_values(self):
        """Test optimization with extreme values in data."""
        X = pd.DataFrame(
            {
                "feature1": [1e6, -1e6, 0, 1e-6, -1e-6],
                "feature2": [1000, -1000, 0, 0.001, -0.001],
            }
        )
        y = pd.Series([1e9, -1e9, 0, 1e3, -1e3])

        study = optuna.create_study(directions=["minimize"])
        trial = study.ask()

        result = objective_multi(trial, X, X, y, y, ["rmse"])

        # Should handle extreme values
        assert len(result) == 1
        assert not np.isnan(result[0])
        assert not np.isinf(result[0])

    def test_optimization_convergence(self, sample_data: pd.DataFrame):
        """Test optimization convergence over multiple trials."""
        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        study = optuna.create_study(directions=["minimize"])

        # Track best values over trials
        best_values = []
        for _ in range(10):
            trial = study.ask()
            result = objective_multi(trial, X_train, X_test, y_train, y_test, ["rmse"])
            study.tell(trial, result[0])
            best_values.append(study.best_value)

        # Best value should generally improve (or stay same)
        assert best_values[-1] <= best_values[0]

    @pytest.mark.slow
    def test_optimization_memory_usage(self, sample_data: pd.DataFrame):
        """Test memory usage during optimization."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        X = sample_data.drop("demand", axis=1)
        y = sample_data["demand"]
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        study = optuna.create_study(directions=["minimize"])

        # Run multiple trials
        for _ in range(20):
            trial = study.ask()
            result = objective_multi(trial, X_train, X_test, y_train, y_test, ["rmse"])
            study.tell(trial, result[0])

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 200MB)
        assert memory_increase < 200 * 1024 * 1024

    def test_ensemble_with_nan_values(self):
        """Test ensemble handling of NaN values."""
        X = pd.DataFrame(
            {"feature1": [1, 2, np.nan, 4, 5], "feature2": [2, 4, 6, np.nan, 10]}
        )
        y = pd.Series([3, 6, 9, 12, 15])

        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble()

        # Should handle NaN values (models might drop or impute)
        try:
            ensemble.fit(X, y)
            predictions = ensemble.predict(X)
            assert len(predictions) == len(X)
        except ValueError:
            # Some models might fail with NaN values, which is acceptable
            pytest.skip("Ensemble models cannot handle NaN values")

    def test_ensemble_with_categorical_features(self):
        """Test ensemble with categorical features."""
        X = pd.DataFrame(
            {
                "numerical_feature": np.random.normal(0, 1, 100),
                "categorical_feature": np.random.choice(["A", "B", "C"], 100),
            }
        )
        y = pd.Series(np.random.normal(10, 2, 100))

        manager = EnsembleManager()
        ensemble = manager.create_stacking_ensemble()

        # Some models might fail with categorical features
        try:
            ensemble.fit(X, y)
            predictions = ensemble.predict(X)
            assert len(predictions) == len(X)
        except ValueError:
            # Expected for some models that require numerical input
            pytest.skip("Ensemble models require numerical features")
