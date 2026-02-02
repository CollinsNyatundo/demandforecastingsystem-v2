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
from sklearn.model_selection import train_test_split

_LOGGER = logging.getLogger(__name__)

# Default constants
DEFAULT_ITERATIONS = 1000
DEFAULT_LEARNING_RATE = 0.1


def optimize_catboost_params(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_trials: int = 50,
    storage=None,
    study_name: str = "catboost_optimization",
) -> dict[str, Any]:
    """Optimize CatBoost hyperparameters using Optuna.

    Args:
        X_train: Training features
        y_train: Training target values
        n_trials: Number of optimization trials
        storage: Optuna storage backend for persistence
        study_name: Name of the Optuna study

    Returns:
        Dictionary with optimized parameters
    """
    _LOGGER.info(f"Starting Optuna optimization with {n_trials} trials...")
    if storage:
        _LOGGER.info(f"Using persistent storage: {type(storage).__name__}")
        _LOGGER.info(f"Study name: {study_name}")
    else:
        _LOGGER.info("Using in-memory storage (study will not persist)")

    # Split data for hyperparameter optimization: 80% train, 20% validation
    # This prevents data leakage by evaluating on unseen data
    X_opt_train, X_opt_val, y_opt_train, y_opt_val = train_test_split(
        X_train, y_train, test_size=0.2, random_state=42, shuffle=True
    )
    _LOGGER.info(
        f"Optimization data split: {len(X_opt_train)} train, {len(X_opt_val)} validation"
    )

    def objective(trial: Trial) -> float:
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "iterations": trial.suggest_int("iterations", 100, 1000),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1e-8, 10.0, log=True),
            "border_count": trial.suggest_int("border_count", 32, 255),
        }

        model = CatBoostRegressor(**params, verbose=False, random_state=42)
        # Train on optimization training set
        model.fit(X_opt_train, y_opt_train)
        # Evaluate on validation set (prevents data leakage)
        pred = model.predict(X_opt_val)
        return np.sqrt(mean_squared_error(y_opt_val, pred))


    try:
        # Create study with or without persistence
        # Use TPESampler with seed for reproducibility
        sampler = TPESampler(seed=42)
        if storage:
            study = optuna.create_study(
                direction="minimize",
                storage=storage,
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

        best_params = study.best_params
        best_params["iterations"] = study.best_params.get(
            "iterations", DEFAULT_ITERATIONS
        )

        _LOGGER.info(f"Best parameters found: {best_params}")
        _LOGGER.info(f"Best RMSE: {study.best_value:.4f}")
        _LOGGER.info(f"Total trials completed: {len(study.trials)}")

        # Add study info to return
        return {
            "best_params": best_params,
            "best_value": study.best_value,
            "n_trials": len(study.trials),
            "study_name": study_name,
            "storage_used": storage is not None,
        }

    except Exception as e:
        _LOGGER.error(f"Optuna optimization failed: {e}")
        # Return default parameters on failure
        return {
            "learning_rate": DEFAULT_LEARNING_RATE,
            "max_depth": 6,
            "iterations": DEFAULT_ITERATIONS,
            "l2_leaf_reg": 1.0,
            "border_count": 128,
        }


def train_catboost_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    optimized_params: dict[str, Any],
    X_test: pd.DataFrame = None,
    y_test: pd.Series = None,
) -> tuple:
    """Train CatBoost model with optimized parameters on FULL training data.

    This trains on 100% of provided training data for maximum model capacity.
    The optimized_params come from Optuna which already did its own 80/20 split,
    so we don't need to hold back data here.

    Args:
        X_train: Training features (ALL training data)
        y_train: Training target values (ALL training data)
        optimized_params: Hyperparameters from optimization
        X_test: Test features (for evaluation, optional)
        y_test: Test target values (for evaluation, optional)

    Returns:
        Tuple of (trained_model, metrics_dict) where metrics_dict contains:
        - rmse: Root Mean Squared Error on test set (or 0.0 if no test set)
        - mae: Mean Absolute Error on test set (or 0.0 if no test set)
        - mape: Mean Absolute Percentage Error on test set (or 0.0 if no test set)
    """
    _LOGGER.info("Training final CatBoost model on FULL training dataset...")

    try:
        # Make a copy of params to avoid mutating the input
        params = optimized_params.copy()

        # Ensure iterations is set
        iterations = params.pop("iterations", DEFAULT_ITERATIONS)

        _LOGGER.info(f"Final training set size: {len(X_train)} (using 100% of data)")

        model = CatBoostRegressor(
            iterations=iterations or DEFAULT_ITERATIONS,
            verbose=False,
            random_state=42,
            **params,
        )

        # Train on FULL dataset (no validation split)
        # Optimization already did hyperparameter tuning with its own validation set
        model.fit(X_train, y_train, verbose=False)

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
        else:
            _LOGGER.warning(
                "No test set provided - returning model without evaluation metrics"
            )

        return model, metrics

    except Exception as e:
        _LOGGER.error(f"Failed to train CatBoost model: {e}")
        raise
