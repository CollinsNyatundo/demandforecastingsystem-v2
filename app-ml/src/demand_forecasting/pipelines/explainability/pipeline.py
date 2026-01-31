"""
Explainability pipeline for SHAP model interpretation.

This pipeline provides model explainability through SHAP values,
feature importance analysis, and MLflow artifact logging.
"""

from kedro.pipeline import Pipeline, node
from .nodes import (
    generate_shap_explanations,
    calculate_feature_importance,
    log_model_artifacts,
    create_explainability_report,
)


def create_pipeline(**kwargs) -> Pipeline:
    """Create the explainability pipeline.

    Returns:
        Pipeline: Kedro pipeline with explainability analysis nodes
    """
    return Pipeline(
        [
            node(
                func=generate_shap_explanations,
                inputs=["catboost_model", "model_input_table"],
                outputs="shap_explanations",
                name="generate_shap_explanations",
            ),
            node(
                func=calculate_feature_importance,
                inputs=["catboost_model"],
                outputs="feature_importance",
                name="calculate_feature_importance",
            ),
            node(
                func=log_model_artifacts,
                inputs=["catboost_model", "shap_explanations", "feature_importance"],
                outputs="artifact_paths",
                name="log_model_artifacts",
            ),
            node(
                func=create_explainability_report,
                inputs=["shap_explanations", "feature_importance"],
                outputs="data_docs_report",
                name="create_explainability_report",
            ),
        ]
    )
