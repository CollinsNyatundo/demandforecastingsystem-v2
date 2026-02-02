"""Enhanced CatBoost training nodes with Optuna persistence and MLflow tracking.

This module extends the base CatBoost implementation with:
- Optuna study persistence to PostgreSQL
- Resume optimization from previous runs
- MLflow experiment tracking integration
- Parallel optimization support
- Enhanced metrics logging

Version: 2.1.0
"""

import logging
import os
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger(__name__)

# Optional imports with graceful degradation
try:
    import optuna
    from optuna.pruners import MedianPruner
    from optuna.samplers import TPESampler
    from optuna.storages import RDBStorage

    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("Optuna not installed. Optimization will not be available.")

try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not installed. Experiment tracking disabled.")


def compute_zero_safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute MAPE with zero-safe divisor matching notebook implementation.

    Args:
        y_true: True values
        y_pred: Predicted values

    Returns:
        MAPE as percentage
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    return (
        np.mean(np.abs((y_true - y_pred) / np.where(y_true == 0, 0.01, y_true))) * 100
    )


def get_optuna_storage(storage_url: str | None = None) -> RDBStorage | None:
    """Get Optuna storage backend for study persistence.

    Args:
        storage_url: PostgreSQL connection URL. If None, uses environment variable.

    Returns:
        RDBStorage instance or None if not available
    """
    if not OPTUNA_AVAILABLE:
        logger.warning("Optuna not available. Cannot create persistent storage.")
        return None

    # Get storage URL from parameter or environment
    if storage_url is None:
        storage_url = os.environ.get(
            "OPTUNA_STORAGE_URL", "postgresql://airflow:airflow@postgres:5432/optuna"
        )

    try:
        storage = RDBStorage(
            url=storage_url,
            engine_kwargs={
                "pool_size": 10,
                "max_overflow": 20,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            },
        )
        logger.info(f"✅ Optuna storage initialized: {storage_url}")
        return storage
    except Exception as e:
        logger.error(f"Failed to initialize Optuna storage: {e}")
        logger.warning("Falling back to in-memory storage (no persistence)")
        return None


def objective_catboost_enhanced(  # noqa: PLR0913
    trial: "optuna.Trial",
    x_train: pd.DataFrame,
    y_train: pd.Series,
    search_space: dict[str, Any],
    catboost_params: dict[str, Any],
    n_splits: int = 3,
    enable_mlflow: bool = False,
) -> float:
    """Enhanced Optuna objective function with MLflow logging support.

    Args:
        trial: Optuna trial object
        x_train: Training features
        y_train: Training target
        search_space: Hyperparameter search space
        catboost_params: Base CatBoost parameters
        n_splits: Number of time series splits for validation
        enable_mlflow: Whether to log to MLflow

    Returns:
        RMSE score for optimization
    """
    # Sample hyperparameters
    params = catboost_params.copy()
    params.update(
        {
            "learning_rate": trial.suggest_float(
                "learning_rate",
                search_space["learning_rate"]["min"],
                search_space["learning_rate"]["max"],
                log=True,
            ),
            "depth": trial.suggest_int(
                "depth", search_space["depth"]["min"], search_space["depth"]["max"]
            ),
            "l2_leaf_reg": trial.suggest_float(
                "l2_leaf_reg",
                search_space["l2_leaf_reg"]["min"],
                search_space["l2_leaf_reg"]["max"],
                log=True,
            ),
        }
    )

    # Optional: Additional hyperparameters for fine-tuning
    if "min_data_in_leaf" in search_space:
        params["min_data_in_leaf"] = trial.suggest_int(
            "min_data_in_leaf",
            search_space["min_data_in_leaf"]["min"],
            search_space["min_data_in_leaf"]["max"],
        )

    if "subsample" in search_space:
        params["subsample"] = trial.suggest_float(
            "subsample",
            search_space["subsample"]["min"],
            search_space["subsample"]["max"],
        )

    # TimeSeries split for validation
    tscv = TimeSeriesSplit(n_splits=n_splits)
    rmse_scores = []
    mae_scores = []
    mape_scores = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(x_train)):
        x_tr, x_val = x_train.iloc[train_idx], x_train.iloc[val_idx]
        y_tr, y_val = y_train.iloc[train_idx], y_train.iloc[val_idx]

        # Train CatBoost with early stopping
        model = CatBoostRegressor(**params, random_seed=42, verbose=0)
        model.fit(
            x_tr,
            y_tr,
            eval_set=(x_val, y_val),
            early_stopping_rounds=50,
            use_best_model=True,
            verbose=False,
        )

        # Predict and evaluate
        preds = model.predict(x_val)
        rmse = np.sqrt(mean_squared_error(y_val, preds))
        mae = mean_absolute_error(y_val, preds)
        mape = compute_zero_safe_mape(y_val.values, preds)

        rmse_scores.append(rmse)
        mae_scores.append(mae)
        mape_scores.append(mape)

        # Report intermediate values for pruning
        trial.report(rmse, fold)

        # Check if trial should be pruned
        if trial.should_prune():
            raise optuna.TrialPruned()

    # Calculate average metrics
    avg_rmse = np.mean(rmse_scores)
    avg_mae = np.mean(mae_scores)
    avg_mape = np.mean(mape_scores)

    # Log to MLflow if enabled
    if enable_mlflow and MLFLOW_AVAILABLE:
        try:
            with mlflow.start_run(nested=True):
                mlflow.log_params(params)
                mlflow.log_metrics(
                    {
                        "cv_rmse_mean": avg_rmse,
                        "cv_rmse_std": np.std(rmse_scores),
                        "cv_mae_mean": avg_mae,
                        "cv_mape_mean": avg_mape,
                    }
                )
        except Exception as e:
            logger.debug(f"Could not log to MLflow: {e}")

    # Store additional metrics as trial attributes
    trial.set_user_attr("mae", avg_mae)
    trial.set_user_attr("mape", avg_mape)
    trial.set_user_attr("cv_scores", rmse_scores)

    return avg_rmse


def optimize_catboost_hyperparameters_enhanced(  # noqa: C901, PLR0913, PLR0915, PLR0912
    model_input_table: pd.DataFrame,
    parameters: dict[str, Any],
    train_fraction: float = 0.8,
    study_name: str | None = None,
    storage_url: str | None = None,
    enable_mlflow: bool = False,
    load_if_exists: bool = True,
) -> tuple[CatBoostRegressor, dict[str, float]]:
    """Optimize CatBoost hyperparameters with persistent Optuna study.

    This function implements:
    - Study persistence to PostgreSQL
    - Resume optimization from previous runs
    - MLflow experiment tracking
    - Parallel optimization support (if using distributed storage)
    - Enhanced metrics logging

    Args:
        model_input_table: Training data with features and target
        parameters: Configuration parameters
        train_fraction: Train/test split fraction
        study_name: Name for Optuna study (enables persistence)
        storage_url: PostgreSQL connection URL for study storage
        enable_mlflow: Whether to log to MLflow
        load_if_exists: Whether to load existing study or create new

    Returns:
        Tuple of (trained_model, metrics_dict)
    """
    if not OPTUNA_AVAILABLE:
        raise ImportError(
            "Optuna is required for hyperparameter optimization. "
            "Install with: pip install optuna"
        )

    # Validate input DataFrame
    if len(model_input_table) == 0:
        raise ValueError("Input DataFrame is empty")

    # Validate required columns
    target_col = "target"
    if target_col not in model_input_table.columns:
        raise ValueError(f"Required column '{target_col}' not found in DataFrame")

    feature_cols = [c for c in model_input_table.columns if c != target_col]
    if len(feature_cols) == 0:
        raise ValueError(
            "No feature columns found. Feature engineering may have failed."
        )

    logger.info(
        f"Training data: {len(model_input_table)} rows, {len(feature_cols)} features"
    )

    # Split data
    train_size = int(len(model_input_table) * train_fraction)
    train_data = model_input_table.iloc[:train_size]
    test_data = model_input_table.iloc[train_size:]

    # Validate that test set is not empty
    if len(test_data) == 0:
        raise ValueError("Test set is empty. Dataset may be too small.")

    X_train = train_data[feature_cols]
    y_train = train_data[target_col]
    X_test = test_data[feature_cols]
    y_test = test_data[target_col]

    logger.info(f"Train: {len(X_train)} rows, Test: {len(X_test)} rows")

    # Get CatBoost parameters
    catboost_params = parameters.get("catboost", {})
    search_space = parameters.get("optuna", {}).get("catboost_search_space", {})
    n_trials = parameters.get("optuna", {}).get("n_trials", 150)

    # Validate search space
    required_params = ["learning_rate", "depth", "l2_leaf_reg"]
    missing = [p for p in required_params if p not in search_space]
    if missing:
        raise ValueError(f"Missing required search space parameters: {missing}")

    # Set up Optuna storage
    storage = get_optuna_storage(storage_url)

    # Generate study name if not provided
    if study_name is None:
        study_name = os.environ.get("OPTUNA_STUDY_NAME", "demand_forecasting_study")

    # Create or load study
    logger.info(f"Setting up Optuna study: {study_name}")

    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
        sampler=TPESampler(seed=42, n_startup_trials=10),
        pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10),
        storage=storage,
        load_if_exists=load_if_exists,
    )

    # Check if study already has trials
    n_existing_trials = len(study.trials)
    if n_existing_trials > 0:
        logger.info(
            f"✅ Loaded existing study with {n_existing_trials} trials. "
            f"Best RMSE so far: {study.best_value:.4f}"
        )
        logger.info(f"Will run {n_trials} additional trials.")
    else:
        logger.info(f"🆕 Created new study. Will run {n_trials} trials.")

    # Define objective function
    def objective(trial: object) -> dict[str, float]:
        return objective_catboost_enhanced(
            trial,
            X_train,
            y_train,
            search_space,
            catboost_params,
            n_splits=3,
            enable_mlflow=enable_mlflow,
        )

    # Optimize
    logger.info("🚀 Starting Optuna optimization...")
    logger.info("Sampler: TPESampler (Bayesian optimization)")
    logger.info("Pruner: MedianPruner (early stopping)")

    if storage:
        logger.info("Storage: PostgreSQL (study persists across runs)")
    else:
        logger.info("Storage: In-memory (study will not persist)")

    study.optimize(
        objective,
        n_trials=n_trials,
        show_progress_bar=False,
        catch=(Exception,),
    )

    # Log study statistics
    logger.info("✅ Optimization complete!")
    logger.info(f"Total trials: {len(study.trials)}")
    logger.info(f"Best trial: #{study.best_trial.number}")
    logger.info(f"Best RMSE: {study.best_value:.4f}")
    logger.info(f"Best parameters: {study.best_trial.params}")

    # Get best parameters
    best_params = catboost_params.copy()
    best_params.update(study.best_trial.params)

    # Train final model on full training data
    logger.info("Training final model with best parameters...")
    final_model = CatBoostRegressor(**best_params, random_seed=42, verbose=0)

    # Use a small validation set for early stopping
    val_size = int(0.15 * len(X_train))
    x_tr, x_val = X_train[:-val_size], X_train[-val_size:]
    y_tr, y_val = y_train[:-val_size], y_train[-val_size:]

    final_model.fit(
        x_tr,
        y_tr,
        eval_set=(x_val, y_val),
        early_stopping_rounds=50,
        use_best_model=True,
        verbose=False,
    )

    # Evaluate on test set
    y_pred = final_model.predict(X_test)

    # Compute metrics
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    mape = compute_zero_safe_mape(y_test.values, y_pred)

    metrics = {
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "mape": round(mape, 4),
        "best_trial": study.best_trial.number,
        "total_trials": len(study.trials),
        "best_params": best_params,
        "study_name": study_name,
        "n_iterations": (
            final_model.get_best_iteration()
            if hasattr(final_model, "get_best_iteration")
            else None
        ),
    }

    # Log final metrics to MLflow
    if enable_mlflow and MLFLOW_AVAILABLE:
        try:
            mlflow.log_metrics(
                {
                    "final_rmse": rmse,
                    "final_mae": mae,
                    "final_mape": mape,
                    "best_iteration": metrics["n_iterations"] or 0,
                }
            )
            mlflow.log_params(
                {"study_name": study_name, "total_trials": len(study.trials)}
            )
        except Exception as e:
            logger.warning(f"Could not log final metrics to MLflow: {e}")

    logger.info(
        f"✅ Final model trained. RMSE: {rmse:.4f}, MAE: {mae:.4f}, MAPE: {mape:.4f}"
    )

    return final_model, metrics


def compare_models_enhanced(
    rf_metrics: dict[str, float], catboost_metrics: dict[str, float]
) -> dict[str, Any]:
    """Compare RandomForest and CatBoost models with enhanced reporting.

    Args:
        rf_metrics: RandomForest metrics
        catboost_metrics: CatBoost metrics

    Returns:
        Dictionary with comparison results and best model recommendation
    """
    winner = (
        "CatBoost" if catboost_metrics["rmse"] < rf_metrics["rmse"] else "RandomForest"
    )
    best_metrics = catboost_metrics if winner == "CatBoost" else rf_metrics

    # Calculate improvements
    rmse_improvement = (
        (rf_metrics["rmse"] - catboost_metrics["rmse"]) / rf_metrics["rmse"]
    ) * 100
    mae_improvement = (
        (rf_metrics["mae"] - catboost_metrics["mae"]) / rf_metrics["mae"]
    ) * 100
    mape_improvement = (
        (rf_metrics["mape"] - catboost_metrics["mape"]) / rf_metrics["mape"]
    ) * 100

    comparison = {
        "random_forest": rf_metrics,
        "catboost": catboost_metrics,
        "winner": winner,
        "best_metrics": best_metrics,
        "rmse_improvement": round(rmse_improvement, 2),
        "mae_improvement": round(mae_improvement, 2),
        "mape_improvement": round(mape_improvement, 2),
        "absolute_rmse_diff": round(
            abs(rf_metrics["rmse"] - catboost_metrics["rmse"]), 4
        ),
        "absolute_mae_diff": round(abs(rf_metrics["mae"] - catboost_metrics["mae"]), 4),
        "recommendation": (
            f"{winner} is recommended with {abs(rmse_improvement):.2f}% better RMSE"
        ),
    }

    logger.info(f"🏆 Model comparison completed. Winner: {comparison['winner']}")
    logger.info(f"RMSE improvement: {comparison['rmse_improvement']:.2f}%")
    logger.info(f"MAE improvement: {comparison['mae_improvement']:.2f}%")
    logger.info(f"MAPE improvement: {comparison['mape_improvement']:.2f}%")

    return comparison


def get_study_history(
    study_name: str, storage_url: str | None = None, n_trials: int = 10
) -> dict[str, Any]:
    """Retrieve optimization history from a persistent Optuna study.

    Args:
        study_name: Name of the Optuna study
        storage_url: PostgreSQL connection URL
        n_trials: Number of recent trials to return

    Returns:
        Dictionary with study history and statistics
    """
    if not OPTUNA_AVAILABLE:
        raise ImportError("Optuna is required to retrieve study history")

    storage = get_optuna_storage(storage_url)
    if storage is None:
        raise ValueError("Could not connect to Optuna storage")

    try:
        study = optuna.load_study(study_name=study_name, storage=storage)

        # Get study statistics
        history = {
            "study_name": study_name,
            "n_trials": len(study.trials),
            "best_trial_number": study.best_trial.number,
            "best_value": study.best_value,
            "best_params": study.best_trial.params,
            "recent_trials": [],
        }

        # Get recent trials
        for trial in study.trials[-n_trials:]:
            history["recent_trials"].append(
                {
                    "number": trial.number,
                    "value": trial.value,
                    "params": trial.params,
                    "state": trial.state.name,
                    "datetime": (
                        trial.datetime_start.isoformat()
                        if trial.datetime_start
                        else None
                    ),
                }
            )

        return history

    except Exception as e:
        logger.error(f"Failed to retrieve study history: {e}")
        raise
