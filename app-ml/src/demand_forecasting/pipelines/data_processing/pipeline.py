"""data processing pipeline definition.

This module defines the Kedro pipeline for data processing.
"""

from kedro.pipeline import Pipeline, node, pipeline

from ...utils.gx_profiler_simple import profile_dataset_gx
from .nodes import preprocess_data


def create_pipeline(**kwargs: object) -> Pipeline:
    """Create the data processing pipeline.

    Returns:
        Pipeline: Kedro pipeline with data processing nodes
    """
    return pipeline(
        [
            node(
                func=preprocess_data,
                inputs="raw_bike_data",
                outputs="preprocessed_bike_data",
                name="preprocess_bike_data_node",
                tags=["training", "inference"],
            ),
            node(
                func=profile_dataset_gx,
                inputs=[
                    "preprocessed_bike_data",
                    "params:dataset_name",
                    "params:data_docs_dir",
                    "params:enable_data_docs",
                ],
                outputs="data_docs_report",
                name="profile_dataset_gx_node",
                tags=["training"],
            ),
        ]
    )
