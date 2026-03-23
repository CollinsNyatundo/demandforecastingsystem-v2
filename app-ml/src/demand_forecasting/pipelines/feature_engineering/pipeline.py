"""Feature Engineering Pipeline.

Transforms raw preprocessed data into engineered features
including temporal features, interactions, and normalization.
"""

from kedro.pipeline import Pipeline, node

from .nodes import (
    create_feature_interactions,
    extract_temporal_features,
    split_features,
    validate_features,
)


def create_pipeline(**kwargs: object) -> Pipeline:
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
            node(
                func=split_features,
                inputs=["validated_features"],
                outputs={
                    "X_train": "X_train",
                    "X_test": "X_test",
                    "y_train": "y_train",
                    "y_test": "y_test",
                },
                name="split_features",
            ),
        ]
    )
