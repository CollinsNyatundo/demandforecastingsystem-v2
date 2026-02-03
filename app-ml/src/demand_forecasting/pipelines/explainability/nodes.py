"""Explainability Pipeline Nodes.

SHAP-based model interpretation and feature importance analysis.
"""

import logging
import tempfile
from typing import Any

import mlflow
import numpy as np
import pandas as pd
import shap
from catboost import CatBoostRegressor

_LOGGER = logging.getLogger(__name__)


def generate_shap_explanations(
    catboost_model: "CatBoostRegressor",
    model_input_table: pd.DataFrame,
) -> dict[str, Any]:
    """Generate SHAP explanations for model predictions.

    Args:
        catboost_model: Trained CatBoost model
        model_input_table: Input data for explanation generation

    Returns:
        Dictionary containing SHAP explanation results
    """
    _LOGGER.debug(
        f"Starting SHAP explanation generation for {len(model_input_table)} samples"
    )

    try:
        # Create SHAP explainer
        explainer = shap.TreeExplainer(catboost_model)
        shap_values = explainer.shap_values(model_input_table)

        # Calculate feature importance
        feature_importance = pd.DataFrame(
            {
                "feature": model_input_table.columns,
                "importance": np.abs(shap_values).mean(0),
            }
        ).sort_values("importance", ascending=False)

        # Prepare explanations dictionary
        shap_explanations = {
            "shap_values": shap_values,
            "feature_names": list(model_input_table.columns),
            "feature_importance": feature_importance,
            "num_samples": len(model_input_table),
            "base_value": explainer.expected_value,
        }

        _LOGGER.info(
            f"SHAP explanations generated for {len(model_input_table)} samples"
        )
        return shap_explanations

    except Exception as e:
        _LOGGER.error(f"Failed to generate SHAP explanations: {e}")
        raise


def calculate_feature_importance(
    catboost_model: "CatBoostRegressor",
) -> pd.DataFrame:
    """Calculate feature importance from CatBoost model.

    Args:
        catboost_model: Trained CatBoost model

    Returns:
        DataFrame with feature importance scores
    """
    _LOGGER.info("Calculating feature importance from CatBoost model...")

    try:
        # Get feature importance from CatBoost model
        feature_names = catboost_model.feature_names_
        importance_scores = catboost_model.get_feature_importance()

        # Create DataFrame with feature importance
        feature_importance = pd.DataFrame({
            "feature": feature_names,
            "importance": importance_scores
        }).sort_values("importance", ascending=False)

        _LOGGER.info(f"Calculated importance for {len(feature_importance)} features")
        return feature_importance

    except Exception as e:
        _LOGGER.error(f"Failed to calculate feature importance: {e}")
        raise


def log_explainability_artifacts(
    catboost_model: "CatBoostRegressor",
    shap_explanations: dict[str, Any],
) -> dict[str, str]:
    """Log explainability artifacts to MLflow."""
    _LOGGER.info("Logging explainability artifacts to MLflow...")

    try:
        with mlflow.start_run(nested=True):
            feature_importance = shap_explanations["feature_importance"]

            # Log feature importance as artifact
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
                importance_path = tmp_file.name
                feature_importance.to_csv(importance_path, index=False)
                mlflow.log_artifact(importance_path, artifact_path="explanations")

            # Log SHAP summary statistics
            shap_summary = {
                "num_samples": shap_explanations["num_samples"],
                "num_features": len(shap_explanations["feature_names"]),
                "base_value": float(shap_explanations["base_value"]),
            }
            mlflow.log_params(shap_summary)

            # Log model with error handling
            try:
                mlflow.catboost.log_model(catboost_model, artifact_path="model")
            except Exception as e:
                _LOGGER.error(f"Failed to log CatBoost model: {e}")
                raise

            active_run = mlflow.active_run()
            artifact_paths: dict[str, str] = {
                "importance_artifact": importance_path,
                "mlflow_run_id": str(active_run.info.run_id) if active_run else "",
            }

            _LOGGER.info("Successfully logged artifacts to MLflow")
            return artifact_paths

    except Exception as e:
        _LOGGER.error(f"Failed to log model artifacts: {e}")
        raise


def log_model_artifacts(
    catboost_model: "CatBoostRegressor",
    shap_explanations: dict[str, Any],
    feature_importance: pd.DataFrame,
) -> dict[str, str]:
    """Log model artifacts to MLflow (alias for log_explainability_artifacts).

    Args:
        catboost_model: Trained CatBoost model
        shap_explanations: SHAP explanation results
        feature_importance: Feature importance DataFrame

    Returns:
        Dictionary with artifact paths
    """
    return log_explainability_artifacts(catboost_model, shap_explanations)


def create_explainability_report(
    shap_explanations: dict[str, Any],
    feature_importance: pd.DataFrame,
) -> str:
    """Create a summary report of model explainability.

    Args:
        shap_explanations: SHAP explanation values
        feature_importance: Feature importance DataFrame

    Returns:
        HTML report as string
    """
    _LOGGER.info("Creating explainability report...")

    try:
        report_html = f"""
        <html>
        <head><title>Model Explainability Report</title></head>
        <body>
        <h1>Model Explainability Analysis</h1>
        <h2>SHAP Analysis</h2>
        <p>Samples analyzed: {shap_explanations['num_samples']}</p>
        <p>Features: {len(shap_explanations['feature_names'])}</p>
        <p>Base value: {shap_explanations['base_value']:.4f}</p>

        <h2>Feature Importance (Top 10)</h2>
        <table border="1">
        <tr><th>Feature</th><th>Importance</th></tr>
        """

        for _, row in feature_importance.head(10).iterrows():
            report_html += (
                f"<tr><td>{row['feature']}</td><td>{row['importance']:.4f}</td></tr>"
            )

        report_html += """
        </table>
        </body>
        </html>
        """

        _LOGGER.info("Explainability report created successfully")
        _LOGGER.debug(f"Explainability report generated ({len(report_html)} bytes)")
        return report_html

    except Exception as e:
        _LOGGER.error(f"Failed to create explainability report: {e}")
        raise
