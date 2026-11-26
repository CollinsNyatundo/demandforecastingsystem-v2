"""Demand Modeling Pipeline.

Orchestrates training of demand forecasting models including
random forest, XGBoost, and CatBoost with hyperparameter optimization.
"""

from kedro.pipeline import Pipeline, node

from .catboost_nodes_enhanced import (
    optimize_catboost_hyperparameters_enhanced as optimize_catboost_params,
)
from .catboost_nodes_enhanced import (
    train_catboost_model,
)
from .nodes import compare_demand_models, train_final_model, train_single_model


def create_pipeline(**kwargs: object) -> Pipeline:
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
                inputs=["X_train", "y_train", "optimized_params", "X_test", "y_test"],
                outputs=["catboost_model", "catboost_metrics"],
                name="train_catboost_model",
            ),
            node(
                func=train_single_model,
                inputs=["X_train", "y_train"],
                outputs="random_forest_model",
                name="train_random_forest",
            ),
            node(
                func=compare_demand_models,
                inputs=["catboost_model", "random_forest_model", "X_test", "y_test"],
                outputs="model_comparison",
                name="compare_demand_models",
            ),
            node(
                func=train_final_model,
                # Pass random_forest_model for reuse (avoids ~30-60s redundant retraining)
                inputs=[
                    "X_train",
                    "y_train",
                    "model_comparison",
                    "catboost_model",
                    "random_forest_model",
                ],
                outputs="final_model",
                name="train_final_model",
            ),
        ]
    )
