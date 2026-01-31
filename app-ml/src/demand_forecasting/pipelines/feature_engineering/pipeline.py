"""Feature Engineering Pipeline

Transforms raw preprocessed data into engineered features
including temporal features, interactions, and normalization.
"""

from kedro.pipeline import Pipeline, node
from .nodes import (
    extract_temporal_features,
    validate_features,
    create_feature_interactions
)


def create_pipeline(**kwargs) -> Pipeline:
    """Create the feature engineering pipeline.
    
    Returns:
        Pipeline: Kedro pipeline with feature engineering nodes
    """
    return Pipeline(
        [
            node(
                func=extract_temporal_features,
                inputs=["preprocessed_bike_data"],
                outputs="temporal_features",
                name="extract_temporal_features",
            ),
            node(
                func=create_feature_interactions,
                inputs=["temporal_features"],
                outputs="engineered_features",
                name="create_feature_interactions",
            ),
            node(
                func=validate_features,
                inputs=["engineered_features"],
                outputs="validated_features",
                name="validate_features",
            ),
        ]
    )
