"""
Explainability Pipeline Nodes
SHAP-based model interpretation and feature importance analysis
"""

import logging
from typing import Dict, Any
import numpy as np
import pandas as pd
import mlflow
import shap
from catboost import CatBoostRegressor

_LOGGER = logging.getLogger(__name__)


def generate_shap_explanations(
    catboost_model: "CatBoostRegressor",
    model_input_table: pd.DataFrame,
) -> Dict[str, Any]:
    _LOGGER.debug(f"Starting SHAP explanation generation for {len(model_input_table)} samples")
    
    try:
        # Create SHAP explainer
        explainer = shap.TreeExplainer(catboost_model)
        shap_values = explainer.shap_values(model_input_table)
        
        # Calculate feature importance
        feature_importance = pd.DataFrame({
            'feature': model_input_table.columns,
            'importance': np.abs(shap_values).mean(0)
        }).sort_values('importance', ascending=False)
        
        # Prepare explanations dictionary
        shap_explanations = {
            'shap_values': shap_values,
            'feature_names': list(model_input_table.columns),
            'feature_importance': feature_importance,
            'num_samples': len(model_input_table),
            'base_value': explainer.expected_value
        }
        
        _LOGGER.info(f"SHAP explanations generated for {len(model_input_table)} samples")
        return shap_explanations
        
    except Exception as e:
        _LOGGER.error(f"Failed to generate SHAP explanations: {e}")
        raise


def log_explainability_artifacts(
    catboost_model: "CatBoostRegressor",
    shap_explanations: Dict[str, Any],
) -> Dict[str, str]:
    """Log explainability artifacts to MLflow"""
    _LOGGER.info("Logging explainability artifacts to MLflow...")
    
    try:
        with mlflow.start_run(nested=True):
            feature_importance = shap_explanations["feature_importance"]
            
            # Log feature importance as artifact
            importance_path = "/tmp/feature_importance.csv"
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
            
            artifact_paths = {
                "importance_artifact": importance_path,
                "mlflow_run_id": mlflow.active_run().info.run_id,
            }
            
            _LOGGER.info("Successfully logged artifacts to MLflow")
            return artifact_paths
            
    except Exception as e:
        _LOGGER.error(f"Failed to log model artifacts: {e}")
        raise


def create_explainability_report(
    shap_explanations: Dict[str, Any],
    feature_importance: pd.DataFrame,
) -> str:
    """
    Create a summary report of model explainability
    
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
            report_html += f"<tr><td>{row['feature']}</td><td>{row['importance']:.4f}</td></tr>"
        
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
