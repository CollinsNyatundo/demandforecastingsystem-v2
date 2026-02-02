"""Demand Modeling Nodes.

Training nodes for random forest and model comparison logic.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

_LOGGER = logging.getLogger(__name__)


def train_single_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    params: dict[str, Any] | None = None,
) -> RandomForestRegressor:
    """Train a single Random Forest model for demand forecasting.

    Args:
        X_train: Training features
        y_train: Training target values
        params: Model hyperparameters

    Returns:
        Trained RandomForestRegressor model
    """
    _LOGGER.info("Training Random Forest model...")

    if params is None:
        params = {
            "n_estimators": 100,
            "max_depth": 15,
            "min_samples_split": 5,
            "random_state": 42,
        }

    try:
        model = RandomForestRegressor(**params)
        model.fit(X_train, y_train)
        _LOGGER.info("Random Forest model trained successfully")
        return model
    except Exception as e:
        _LOGGER.error(f"Failed to train Random Forest model: {e}")
        raise


def compare_demand_models(
    catboost_model,
    random_forest_model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    """Compare performance of CatBoost and Random Forest models for demand forecasting.

    Follows ML system design best practices for demand forecasting systems.
    Uses consistent metrics aligned with notebook ground truth and production requirements.

    Args:
        catboost_model: Trained CatBoost model from catboost_nodes.train_catboost_model()
        random_forest_model: Trained Random Forest model from train_single_model()
        X_test: Test features for evaluation
        y_test: Test target values for evaluation

    Returns:
        Dictionary with comprehensive comparison metrics for each model:
        {
            "catboost": {"rmse": float, "r2": float, "mae": float},
            "random_forest": {"rmse": float, "r2": float, "mae": float},
            "best_model": str,  # "catboost" or "random_forest"
            "comparison_timestamp": str
        }

    Raises:
        ValueError: If models are invalid or evaluation fails
    """
    _LOGGER.info("Starting model comparison for demand forecasting...")

    # Validate model inputs
    if catboost_model is None or not hasattr(catboost_model, 'predict'):
        raise ValueError("Invalid CatBoost model: model must have predict() method")

    if random_forest_model is None or not hasattr(random_forest_model, 'predict'):
        raise ValueError("Invalid Random Forest model: model must have predict() method")

    if X_test is None or y_test is None or len(X_test) != len(y_test):
        raise ValueError("Invalid test data: X_test and y_test must have same length and not be None")

    try:
        # Get predictions from both models
        _LOGGER.info(f"Evaluating models on {len(X_test)} test samples...")

        cb_pred = catboost_model.predict(X_test)
        rf_pred = random_forest_model.predict(X_test)

        # Calculate metrics aligned with modeling notebook's compute_metrics function
        comparison = {
            "catboost": {
                "rmse": np.sqrt(mean_squared_error(y_test, cb_pred)),
                "r2": r2_score(y_test, cb_pred),
                "mae": mean_absolute_error(y_test, cb_pred),
            },
            "random_forest": {
                "rmse": np.sqrt(mean_squared_error(y_test, rf_pred)),
                "r2": r2_score(y_test, rf_pred),
                "mae": mean_absolute_error(y_test, rf_pred),
            },
        }

        # Determine best model based on RMSE (primary metric for demand forecasting)
        # Lower RMSE indicates better predictive performance
        cb_rmse = comparison["catboost"]["rmse"]
        rf_rmse = comparison["random_forest"]["rmse"]

        best_model = "catboost" if cb_rmse < rf_rmse else "random_forest"
        comparison["best_model"] = best_model

        # Add timestamp for audit trail (important for ML systems)
        import datetime
        comparison["comparison_timestamp"] = datetime.datetime.now().isoformat()

        # Comprehensive logging for production monitoring
        _LOGGER.info("Model comparison completed:")
        _LOGGER.info(f"  CatBoost - RMSE: {cb_rmse:.4f}, R2: {comparison['catboost']['r2']:.4f}, MAE: {comparison['catboost']['mae']:.4f}")
        _LOGGER.info(f"  Random Forest - RMSE: {rf_rmse:.4f}, R2: {comparison['random_forest']['r2']:.4f}, MAE: {comparison['random_forest']['mae']:.4f}")
        _LOGGER.info(f"  Best model: {best_model} (RMSE improvement: {abs(cb_rmse - rf_rmse):.4f})")

        # Validate metrics are reasonable (defensive programming)
        for model_name, metrics in comparison.items():
            if model_name in ["catboost", "random_forest"]:
                for metric_name, value in metrics.items():
                    if not isinstance(value, (int, float)) or value < 0:
                        raise ValueError(
                            f"Invalid {metric_name} for {model_name}: {value}. "
                            f"Metrics must be non-negative numbers."
                        )

        return comparison

    except Exception as e:
        _LOGGER.error(f"Model comparison failed: {e}")
        raise ValueError(f"Failed to compare models: {e!s}") from e


def train_final_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_comparison: dict[str, Any],
    catboost_model: Any = None,
) -> Any:
    """Train the final model based on validated comparison results.

    Follows defensive programming and explicit validation principles.
    Ensures model selection integrity and comprehensive audit logging.

    Args:
        X_train: Training features
        y_train: Training target values
        model_comparison: Results from model comparison with structure validation
        catboost_model: Trained CatBoost model (if available)

    Returns:
        Trained final model object (for Kedro catalog persistence)

    Raises:
        ValueError: If model_comparison structure is invalid or metrics are missing
    """
    _LOGGER.info("Training final model with comprehensive validation...")

    # Validate model_comparison structure
    required_keys = ["best_model", "catboost", "random_forest"]
    missing_keys = [k for k in required_keys if k not in model_comparison]

    if missing_keys:
        raise ValueError(
            f"Invalid model_comparison structure. Missing keys: {missing_keys}. "
            f"Comparison must contain 'best_model', 'catboost', and 'random_forest' keys. "
            f"Check compare_demand_models() output structure."
        )

    best_model_name = model_comparison["best_model"]

    # Explicit validation without fallback
    valid_models = ["catboost", "random_forest"]
    if best_model_name not in valid_models:
        raise ValueError(
            f"Invalid best model selection: '{best_model_name}'. "
            f"Must be one of {valid_models}. "
            f"Check compare_demand_models() output and ensure proper model comparison."
        )

    # Verify metrics exist for chosen model
    chosen_metrics = model_comparison.get(best_model_name, {})
    if not chosen_metrics or "rmse" not in chosen_metrics:
        raise ValueError(
            f"No valid metrics found for chosen model '{best_model_name}'. "
            f"Model comparison may be corrupted or incomplete. "
            f"Expected metrics: rmse, r2, mae"
        )

    # Additional validation: check metrics are reasonable
    if not isinstance(chosen_metrics["rmse"], (int, float)) or chosen_metrics["rmse"] < 0:
        raise ValueError(
            f"Invalid RMSE value for '{best_model_name}': {chosen_metrics['rmse']}. "
            f"RMSE must be a non-negative number."
        )

    # Log comprehensive decision information
    _LOGGER.info(
        f"Selected {best_model_name} as final model. "
        f"Metrics - RMSE: {chosen_metrics['rmse']:.4f}, "
        f"R2: {chosen_metrics.get('r2', 'N/A'):.4f}, "
        f"MAE: {chosen_metrics.get('mae', 'N/A'):.4f}"
    )

    # Model selection logic with explicit validation
    if best_model_name == "catboost":
        if catboost_model is None:
            _LOGGER.error(
                "CatBoost selected as best model but model object not provided. "
                "This indicates a pipeline dependency issue. "
                "Ensure catboost_model is properly passed from previous pipeline nodes."
            )
            raise ValueError(
                "CatBoost model selected but not provided to function. "
                "Check pipeline dependencies and ensure proper model passing."
            )

        # Validate catboost model has predict method
        if not hasattr(catboost_model, 'predict'):
            raise ValueError(
                "Provided CatBoost model is invalid - missing predict method. "
                "Ensure model is properly trained before passing to this function."
            )

        final_model = catboost_model
        _LOGGER.info("Using validated CatBoost model as final model")

    else:  # random_forest
        _LOGGER.info("Training new Random Forest as final model")
        final_model = train_single_model(X_train, y_train)

        # Validate trained model
        if not hasattr(final_model, 'predict'):
            raise ValueError(
                "Failed to train valid Random Forest model - missing predict method."
            )

    _LOGGER.info(f"Final model trained and validated successfully ({best_model_name})")
    return final_model
