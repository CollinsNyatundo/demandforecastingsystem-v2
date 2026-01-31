"""Project pipelines."""

from __future__ import annotations

from kedro.pipeline import Pipeline

from demand_forecasting.pipelines import demand_modeling as dm
from demand_forecasting.pipelines import data_processing as dp
from demand_forecasting.pipelines import explainability as ex


def register_pipelines() -> dict[str, Pipeline]:
    """Register the project's pipelines.

    Returns:
        A mapping from pipeline names to ``Pipeline`` objects.
    """
    # Create demand modeling pipeline
    demand_modeling_pipeline = dm.create_pipeline()

    # Create data processing pipeline
    data_processing_pipeline = dp.create_pipeline()

    # Create explainability pipeline
    explainability_pipeline = ex.create_pipeline()

    # Create ML pipeline for serving
    ml_pipeline = data_processing_pipeline + demand_modeling_pipeline

    return {
        "__default__": ml_pipeline,
        "demand_modeling": demand_modeling_pipeline,
        "data_processing": data_processing_pipeline,
        "explainability": explainability_pipeline,
        "training": ml_pipeline,
    }
