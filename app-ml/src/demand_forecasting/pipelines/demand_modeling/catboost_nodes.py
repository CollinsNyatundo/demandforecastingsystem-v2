"""CatBoost Training Nodes.

Hyperparameter optimization and model training using CatBoost and Optuna.
"""

import logging
from typing import Any

import numpy as np
import optuna
import pandas as pd
from catboost import CatBoostRegressor
from optuna.samplers import TPESampler
from optuna.trial import Trial
from sklearn.metrics import mean_absolute_error, mean_squared_error

# sklearn.model_selection.train_test_split removed - using time-based split for time series

# Optional ClearML integration for experiment tracking
try:
    from demand_forecasting.integrations.clearml_integration import (
        init_clearml_task,
        log_metrics,
        log_optuna_study,
    )

    _CLEARML_AVAILABLE = True
except ImportError:
    _CLEARML_AVAILABLE = False
    def init_clearml_task(**kwargs):
        return None  # type: ignore[misc]
    def log_metrics(*args):
        return None  # type: ignore[misc]
    def log_optuna_study(*args):
        return None  # type: ignore[misc]

_LOGGER = logging.getLogger(__name__)

# Default constants
DEFAULT_ITERATIONS = 1000
DEFAULT_LEARNING_RATE = 0.1


def _ensure_series(data: pd.DataFrame | pd.Series) -> pd.Series:
    """Convert DataFrame to Series if needed.

    Args:
        data: Input data, either DataFrame or Series

    Returns:
        Series with the data
    """
    if isinstance(data, pd.DataFrame):
        if data.shape[1] == 1:
            return data.iloc[:, 0]
        if "target" in data.columns:
            return data["target"]
        raise ValueError(
            f"Cannot convert DataFrame with columns {data.columns} to Series"
        )
    return data


def optimize_catboost_params(
    X_train: pd.DataFrame,
    y_train: pd.Series | pd.DataFrame,
    n_trials: int = 50,
    storage: object | None = None,
    study_name: str = "catboost_optimization",
) -> dict[str, Any]:
    """Optimize CatBoost hyperparameters using Optuna.

    Args:
        X_train: Training features
        y_train: Training target values (Series or single-column DataFrame)
        n_trials: Number of optimization trials
        storage: Optuna storage backend for persistence
        study_name: Name of the Optuna study

    Returns:
        Dictionary with optimized parameters
    """
    # Convert DataFrame to Series if needed
    y_train = _ensure_series(y_train)

    _LOGGER.info(f"Starting Optuna optimization with {n_trials} trials...")
    if storage:
        _LOGGER.info(f"Using persistent storage: {type(storage).__name__}")
        _LOGGER.info(f"Study name: {study_name}")
    else:
        _LOGGER.info("Using in-memory storage (study will not persist)")

    # Initialize ClearML task for hyperparameter optimization tracking
    clearml_task = None
    if _CLEARML_AVAILABLE:
        clearml_task = init_clearml_task(
            project_name="demand_forecasting",
            task_name=f"hyperopt_{study_name}",
            task_type="optimizer",
        )

    # TIME-BASED split for hyperparameter optimization: 80% train, 20% validation
    # CRITICAL for time series: validation data must be AFTER training data
    # This mirrors how the model will be used in production (predict future from past)
    # Using shuffle=False to preserve temporal order
    train_size = int(0.8 * len(X_train))
    X_opt_train = X_train.iloc[:train_size]
    X_opt_val = X_train.iloc[train_size:]
    y_opt_train = y_train.iloc[:train_size]
    y_opt_val = y_train.iloc[train_size:]
    _LOGGER.info(
        f"TIME-BASED optimization split: {len(X_opt_train)} train (first 80%), "
        f"{len(X_opt_val)} validation (last 20%)"
    )

    def objective(trial: Trial) -> float:
        # Expanded search space with additional CatBoost parameters
        # for better model performance based on research
        # Using log-scale for exponential parameters (AUDIT-H1)
        params = {
            "learning_rate": trial.suggest_float(
                "learning_rate", 0.01, 0.2, log=True
            ),  # Log scale
            "depth": trial.suggest_int("depth", 3, 8),
            "iterations": trial.suggest_int("iterations", 500, 2000),  # Now tunable
            "l2_leaf_reg": trial.suggest_float(
                "l2_leaf_reg", 0.5, 5.0, log=True
            ),  # Log scale
            # Additional parameters for better performance
            "border_count": trial.suggest_int("border_count", 32, 255),
            "random_strength": trial.suggest_float("random_strength", 0.0, 1.0),
            "bagging_temperature": trial.suggest_float("bagging_temperature", 0.0, 1.0),
            "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 1, 100),
            "loss_function": "RMSE",
        }

        # train_dir to writable location for Docker permission fix
        model = CatBoostRegressor(
            **params,
            verbose=False,
            random_seed=42,
            train_dir="/tmp/catboost_optuna",
            allow_writing_files=True,
        )
        # Train with early stopping (matching notebook approach)
        # This prevents overfitting and finds optimal iteration count
        model.fit(
            X_opt_train,
            y_opt_train,
            eval_set=(X_opt_val, y_opt_val),
            early_stopping_rounds=100,  # Match notebook
            use_best_model=True,
            verbose=False,
        )

        # Store best iteration for later use (matching notebook)
        trial.set_user_attr("best_iteration", model.get_best_iteration())

        # Evaluate on validation set
        pred = model.predict(X_opt_val)
        return float(np.sqrt(mean_squared_error(y_opt_val, pred)))

    try:
        # Create study with or without persistence
        # Use TPESampler with seed for reproducibility
        sampler = TPESampler(seed=42)
        if storage:
            study = optuna.create_study(
                direction="minimize",
                storage=storage,  # type: ignore[arg-type]
                study_name=study_name,
                load_if_exists=True,  # Resume existing study
                sampler=sampler,  # Use seeded sampler for reproducibility
            )
            _LOGGER.info(
                f"Loaded/created study '{study_name}' with {len(study.trials)} existing trials"
            )
        else:
            study = optuna.create_study(direction="minimize", sampler=sampler)
            _LOGGER.info("Created new in-memory study")

        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        # Get best trial parameters
        best_params = study.best_params.copy()

        # Get best iteration from early stopping (matching notebook approach)
        # Notebook: best_params.update({"iterations": best_trial.user_attrs["best_iteration"]})
        best_iteration = study.best_trial.user_attrs.get(
            "best_iteration", DEFAULT_ITERATIONS
        )
        best_params["iterations"] = best_iteration
        best_params["loss_function"] = "RMSE"
        best_params["verbose"] = False

        _LOGGER.info(f"Best parameters found: {best_params}")
        _LOGGER.info(f"Best iteration (from early stopping): {best_iteration}")
        _LOGGER.info(f"Best RMSE: {study.best_value:.4f}")
        _LOGGER.info(f"Total trials completed: {len(study.trials)}")

        # Log Optuna study visualizations to ClearML
        if clearml_task:
            log_optuna_study(clearml_task, study)
            log_metrics(
                clearml_task,
                {"best_rmse": study.best_value, "n_trials": len(study.trials)},
            )
            clearml_task.close()

        # Return flat params dict for direct use in train_catboost_model
        # Include metadata as underscore-prefixed keys that will be ignored
        return best_params

    except Exception as e:
        _LOGGER.error(f"Optuna optimization failed: {e}")
        # Close ClearML task on failure
        if clearml_task:
            clearml_task.mark_failed(status_reason=str(e))
        # Return default parameters on failure
        # Return default parameters matching notebook's best params structure
        return {
            "learning_rate": DEFAULT_LEARNING_RATE,
            "depth": 6,  # CatBoost uses 'depth', not 'max_depth'
            "iterations": DEFAULT_ITERATIONS,
            "l2_leaf_reg": 1.0,
            "loss_function": "RMSE",
            "verbose": False,
        }


def train_catboost_model(
    X_train: pd.DataFrame,
    y_train: pd.Series | pd.DataFrame,
    optimized_params: dict[str, Any],
    X_test: pd.DataFrame | None = None,
    y_test: pd.Series | pd.DataFrame | None = None,
) -> tuple:
    """Train CatBoost model with optimized parameters on FULL training data.

    This trains on 100% of provided training data for maximum model capacity.
    The optimized_params come from Optuna which already did its own 80/20 split,
    so we don't need to hold back data here.

    Args:
        X_train: Training features (ALL training data)
        y_train: Training target values (ALL training data) - Series or single-column DataFrame
        optimized_params: Hyperparameters from optimization
        X_test: Test features (for evaluation, optional)
        y_test: Test target values (for evaluation, optional) - Series or single-column DataFrame

    Returns:
        Tuple of (trained_model, metrics_dict) where metrics_dict contains:
        - rmse: Root Mean Squared Error on test set (or 0.0 if no test set)
        - mae: Mean Absolute Error on test set (or 0.0 if no test set)
        - mape: Mean Absolute Percentage Error on test set (or 0.0 if no test set)
    """
    _LOGGER.info("Training final CatBoost model on FULL training dataset...")

    # Convert DataFrame to Series if needed
    y_train = _ensure_series(y_train)
    if y_test is not None:
        y_test = _ensure_series(y_test)

    # Initialize ClearML task for training tracking
    clearml_task = None
    if _CLEARML_AVAILABLE:
        clearml_task = init_clearml_task(
            project_name="demand_forecasting",
            task_name="catboost_training",
            task_type="training",
        )

    try:
        # Make a copy of params to avoid mutating the input
        params = optimized_params.copy()

        # Ensure iterations is set
        iterations = params.pop("iterations", DEFAULT_ITERATIONS)

        _LOGGER.info(f"Final training set size: {len(X_train)} (using 100% of data)")

        # CatBoost uses 'random_seed', not 'random_state' (matching notebook)
        # train_dir set to /tmp to avoid Docker permission errors
        model = CatBoostRegressor(
            iterations=iterations or DEFAULT_ITERATIONS,
            random_seed=42,
            train_dir="/tmp/catboost_info",  # Writable directory for Docker
            allow_writing_files=True,
            **params,
        )

        # Train on FULL dataset (no validation split)
        # Optimization already did hyperparameter tuning with its own validation set
        # Matching notebook: final_model.fit(x_train, y_train)
        model.fit(X_train, y_train)

        _LOGGER.info("CatBoost model trained successfully on full dataset")

        # Evaluate on test set if provided (matches notebook strategy)
        metrics = {
            "rmse": 0.0,
            "mae": 0.0,
            "mape": 0.0,
            "model_trained": True,
            "test_set_used": False,
        }

        if X_test is not None and y_test is not None:
            _LOGGER.info(f"Computing metrics on test set ({len(X_test)} samples)...")

            # Predict on test set
            y_pred = model.predict(X_test)

            # Compute metrics (same as notebook)
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))

            # MAPE calculation (same as notebook)
            y_test_array = np.array(y_test)
            y_pred_array = np.array(y_pred)
            mape = (
                np.mean(
                    np.abs(
                        (y_test_array - y_pred_array)
                        / np.where(y_test_array == 0, 0.01, y_test_array)
                    )
                )
                * 100
            )

            metrics = {
                "rmse": round(rmse, 2),
                "mae": round(mae, 2),
                "mape": round(mape, 2),
                "model_trained": True,
                "test_set_used": True,
                "test_samples": len(X_test),
            }

            _LOGGER.info("✅ CatBoost evaluation on test set:")
            _LOGGER.info(f"   RMSE: {metrics['rmse']:.4f}")
            _LOGGER.info(f"   MAE: {metrics['mae']:.4f}")
            _LOGGER.info(f"   MAPE: {metrics['mape']:.4f}%")

            # Log metrics to ClearML
            if clearml_task:
                log_metrics(
                    clearml_task,
                    {
                        "rmse": metrics["rmse"],
                        "mae": metrics["mae"],
                        "mape": metrics["mape"],
                    },
                )
        else:
            _LOGGER.warning(
                "No test set provided - returning model without evaluation metrics"
            )

        # Close ClearML task after successful training
        if clearml_task:
            clearml_task.close()

        return model, metrics

    except Exception as e:
        _LOGGER.error(f"Failed to train CatBoost model: {e}")
        if clearml_task:
            clearml_task.mark_failed(status_reason=str(e))
        raise
