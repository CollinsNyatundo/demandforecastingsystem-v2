"""
Demand Modeling Nodes

Training nodes for random forest and model comparison logic.
"""

import logging
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

_LOGGER = logging.getLogger(__name__)


def train_single_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    params: Dict[str, Any] = None,
) -> RandomForestRegressor:
    """
    Train a single Random Forest model for demand forecasting.
    
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
            "random_state": 42
        }
    
    try:
        model = RandomForestRegressor(**params)
        model.fit(X_train, y_train)
        _LOGGER.info("Random Forest model trained successfully")
        return model
    except Exception as e:
        _LOGGER.error(f"Failed to train Random Forest model: {e}")
        raise


def compare_models(
    catboost_model,
    random_forest_model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Dict[str, Any]:
    """
    Compare performance of CatBoost and Random Forest models.
    
    Args:
        catboost_model: Trained CatBoost model
        random_forest_model: Trained Random Forest model
        X_test: Test features
        y_test: Test target values
        
    Returns:
        Dictionary with comparison metrics for each model
    """
    _LOGGER.info("Comparing models...")
    
    try:
        # Get predictions
        cb_pred = catboost_model.predict(X_test)
        rf_pred = random_forest_model.predict(X_test)
        
        # Calculate metrics
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
            "best_model": "catboost" if np.sqrt(mean_squared_error(y_test, cb_pred)) < np.sqrt(mean_squared_error(y_test, rf_pred)) else "random_forest"
        }
        
        _LOGGER.info(f"Best model: {comparison['best_model']}")
        return comparison
        
    except Exception as e:
        _LOGGER.error(f"Failed to compare models: {e}")
        raise


def train_final_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_comparison: Dict[str, Any],
    catboost_model: Any = None,
) -> Any:
    """
    Train the final model based on comparison results.
    
    Args:
        X_train: Training features
        y_train: Training target values
        model_comparison: Results from model comparison
        catboost_model: Trained CatBoost model (if available)
        
    Returns:
        Trained final model object (for Kedro catalog persistence)
    """
    _LOGGER.info("Training final model...")
    
    try:
        best_model_name = model_comparison.get("best_model", "random_forest")
        
        # Validate best_model selection before proceeding
        if not best_model_name or best_model_name not in ["catboost", "random_forest"]:
            raise ValueError(f"Invalid best model selection: {best_model_name}")
        
        if best_model_name == "catboost":
            _LOGGER.info("Using CatBoost as final model")
            if catboost_model is not None:
                final_model = catboost_model
                _LOGGER.info("Using provided CatBoost model")
            else:
                # Fallback: retrain if model not provided
                _LOGGER.warning("CatBoost model not provided, retraining...")
                from .catboost_nodes import train_catboost_model, optimize_catboost_params
                
                # Get optimized parameters for CatBoost
                optimized_params = optimize_catboost_params(X_train, y_train, n_trials=10)
                final_model = train_catboost_model(X_train, y_train, optimized_params)
        else:
            _LOGGER.info("Using Random Forest as final model")
            final_model = train_single_model(X_train, y_train)
        
        _LOGGER.info(f"Final model trained ({best_model_name})")
        return final_model
        
    except Exception as e:
        _LOGGER.error(f"Failed to train final model: {e}")
        raise
