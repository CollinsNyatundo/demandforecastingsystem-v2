"""demand modeling pipeline definition.

This module defines the Kedro pipeline for demand modeling."""

"""Demand Modeling Pipeline

Orchestrates training of demand forecasting models including
random forest, XGBoost, and CatBoost with hyperparameter optimization.
""" 
from kedro.pipeline import Pipeline, node
from .nodes import (
    train_single_model,
    train_final_model,
    compare_models
)
from .catboost_nodes import (
    optimize_catboost_params,
    train_catboost_model
)
 
def create_pipeline(**kwargs) -> Pipeline:
    """Create the demand modeling pipeline.
    
    Returns:
        Pipeline: Kedro pipeline with model training nodes
    """
    return Pipeline(
        [
            node(
                func=optimize_catboost_params,
                inputs=["X_train", "y_train"],
                outputs="optimized_params",
                name="optimize_catboost_params",
            ),
            node(
                func=train_catboost_model,
                inputs=["X_train", "y_train", "optimized_params"],
                outputs="catboost_model",
                name="train_catboost_model",
            ),
            node(
                func=train_single_model,
                inputs=["X_train", "y_train"],
                outputs="random_forest_model",
                name="train_random_forest",
            ),
            node(
                func=compare_models,
                inputs=["catboost_model", "random_forest_model", "X_test", "y_test"],
                outputs="model_comparison",
                name="compare_models",
            ),
            node(
                func=train_final_model,
                inputs=["X_train", "y_train", "model_comparison", "catboost_model"],
                outputs="final_model",
                name="train_final_model",
            ),
        ]
    )
