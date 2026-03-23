"""Project pipelines."""

from __future__ import annotations

import logging

from kedro.pipeline import Pipeline

from demand_forecasting.pipelines import data_processing as dp
from demand_forecasting.pipelines import demand_modeling as dm
from demand_forecasting.pipelines import feature_engineering as fe

# Explainability pipeline requires SHAP which depends on numba
# Make it optional to allow running without numba
try:
    from demand_forecasting.pipelines import explainability as ex

    EXPLAINABILITY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Explainability pipeline not available: {e}")
    ex = None
    EXPLAINABILITY_AVAILABLE = False


def register_pipelines() -> dict[str, Pipeline]:
    """Register the project's pipelines.

    Returns:
        A mapping from pipeline names to ``Pipeline`` objects.
    """
    # Create individual pipelines
    data_processing_pipeline = dp.create_pipeline()
    feature_engineering_pipeline = fe.create_pipeline()
    demand_modeling_pipeline = dm.create_pipeline()

    # Create complete ML pipeline with proper flow:
    # data_processing -> feature_engineering -> demand_modeling
    ml_pipeline = (
        data_processing_pipeline
        + feature_engineering_pipeline
        + demand_modeling_pipeline
    )

    pipelines = {
        "__default__": ml_pipeline,
        "data_processing": data_processing_pipeline,
        "feature_engineering": feature_engineering_pipeline,
        "demand_modeling": demand_modeling_pipeline,
        "training": ml_pipeline,
    }

    # Add explainability pipeline if available (requires SHAP/numba)
    if EXPLAINABILITY_AVAILABLE and ex is not None:
        explainability_pipeline = ex.create_pipeline()
        pipelines["explainability"] = explainability_pipeline

    return pipelines
