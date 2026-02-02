"""Model explainability using SHAP for demand forecasting."""

import logging
from typing import Any

import numpy as np
import pandas as pd
import shap
from plotly.graph_objects import Figure

logger = logging.getLogger(__name__)


class ModelExplainer:
    """Generate model explanations using SHAP."""

    def __init__(self, model, data: pd.DataFrame, model_type: str = "tree"):
        """Initialize SHAP explainer.

        Args:
            model: Trained model to explain
            data: Reference dataset for explanation
            model_type: Type of model ('tree', 'linear', 'deep', etc.)
        """
        self.model = model
        self.data = data
        self.model_type = model_type.lower()

        try:
            # Initialize appropriate SHAP explainer
            if self.model_type == "tree":
                self.explainer = shap.TreeExplainer(model)
            elif self.model_type == "linear":
                self.explainer = shap.LinearExplainer(model, data)
            elif self.model_type == "deep":
                self.explainer = shap.DeepExplainer(model, data)
            else:
                # Default to TreeExplainer for CatBoost
                self.explainer = shap.TreeExplainer(model)

            # Calculate SHAP values for the dataset
            logger.info(f"Computing SHAP values for {len(data)} samples...")
            self.shap_values = self.explainer.shap_values(data)

            # Handle multi-output case
            if isinstance(self.shap_values, list):
                self.shap_values = self.shap_values[0]  # Take first output

            logger.info("SHAP explainer initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize SHAP explainer: {e}")
            raise

    def global_importance(self, top_n: int | None = None) -> pd.DataFrame:
        """Get global feature importance.

        Args:
            top_n: Number of top features to return

        Returns:
            DataFrame with feature importance rankings
        """
        try:
            # Calculate mean absolute SHAP values
            importance = np.abs(self.shap_values).mean(axis=0)

            # Create importance DataFrame
            importance_df = pd.DataFrame(
                {
                    "feature": self.data.columns,
                    "importance": importance,
                    "mean_shap_value": self.shap_values.mean(axis=0),
                    "std_shap_value": self.shap_values.std(axis=0),
                }
            ).sort_values("importance", ascending=False)

            if top_n:
                importance_df = importance_df.head(top_n)

            # Add rank
            importance_df["rank"] = range(1, len(importance_df) + 1)

            return importance_df.reset_index(drop=True)

        except Exception as e:
            logger.error(f"Error calculating global importance: {e}")
            raise

    def explain_prediction(
        self, sample_idx: int, feature_names: list[str] | None = None
    ) -> dict[str, Any]:
        """Explain a single prediction.

        Args:
            sample_idx: Index of the sample to explain
            feature_names: Optional feature names (uses data columns if None)

        Returns:
            Dictionary with prediction explanation
        """
        try:
            if sample_idx >= len(self.data):
                raise ValueError(f"Sample index {sample_idx} out of range")

            # Get sample and SHAP values
            sample = self.data.iloc[sample_idx]
            shap_vals = self.shap_values[sample_idx]

            # Use provided feature names or default to data columns
            if feature_names is None:
                feature_names = list(self.data.columns)

            # Get prediction
            if hasattr(self.model, "predict"):
                prediction = self.model.predict(sample.values.reshape(1, -1))[0]
            else:
                prediction = "unknown"

            # Create feature contributions dictionary
            contributions = dict(zip(feature_names, shap_vals, strict=False))

            # Get top contributors (positive and negative)
            sorted_contributions = sorted(
                contributions.items(), key=lambda x: abs(x[1]), reverse=True
            )
            top_positive = [(f, v) for f, v in sorted_contributions if v > 0][:5]
            top_negative = [(f, v) for f, v in sorted_contributions if v < 0][:5]

            return {
                "sample_index": sample_idx,
                "prediction": (
                    float(prediction)
                    if isinstance(prediction, (int, float))
                    else prediction
                ),
                "base_value": (
                    float(self.explainer.expected_value)
                    if hasattr(self.explainer, "expected_value")
                    else 0.0
                ),
                "shap_values": contributions,
                "feature_values": dict(zip(feature_names, sample.values, strict=False)),
                "top_positive_contributors": top_positive,
                "top_negative_contributors": top_negative,
                "top_contributors": sorted_contributions[:5],
                "total_contribution": float(np.sum(shap_vals)),
            }

        except Exception as e:
            logger.error(f"Error explaining prediction: {e}")
            raise

    def create_summary_plot(
        self, plot_type: str = "bar", max_features: int = 20
    ) -> Figure:
        """Create SHAP summary plot using Plotly.

        Args:
            plot_type: Type of plot ('bar', 'beeswarm', 'violin')
            max_features: Maximum number of features to show

        Returns:
            Plotly Figure object
        """
        try:
            importance_df = self.global_importance(max_features)

            if plot_type == "bar":
                fig = Figure()
                fig.add_trace(
                    {
                        "type": "bar",
                        "x": importance_df["importance"],
                        "y": importance_df["feature"],
                        "orientation": "h",
                        "marker": {"color": "lightblue"},
                    }
                )

                fig.update_layout(
                    title="Feature Importance (Mean |SHAP value|)",
                    xaxis_title="Mean |SHAP value|",
                    yaxis_title="Features",
                    height=max(400, max_features * 30),
                    yaxis={"categoryorder": "total ascending"},
                )

            elif plot_type == "beeswarm":
                # Create beeswarm plot
                fig = Figure()

                for i, feature in enumerate(importance_df["feature"]):
                    feature_idx = list(self.data.columns).index(feature)
                    shap_vals = self.shap_values[:, feature_idx]
                    feature_vals = self.data.iloc[:, feature_idx]

                    fig.add_trace(
                        {
                            "type": "scatter",
                            "x": shap_vals,
                            "y": [i] * len(shap_vals),
                            "mode": "markers",
                            "marker": {
                                "color": feature_vals,
                                "colorscale": "RdBu",
                                "showscale": i
                                == 0,  # Only show colorbar for first feature
                                "colorbar": (
                                    {"title": "Feature Value"} if i == 0 else None
                                ),
                            },
                            "name": feature,
                            "showlegend": False,
                        }
                    )

                fig.update_layout(
                    title="SHAP Beeswarm Plot",
                    xaxis_title="SHAP value",
                    yaxis_title="Features",
                    yaxis={
                        "tickvals": list(range(len(importance_df))),
                        "ticktext": importance_df["feature"].tolist(),
                    },
                    height=max(400, max_features * 30),
                )

            else:  # violin plot
                fig = Figure()

                for i, feature in enumerate(importance_df["feature"]):
                    feature_idx = list(self.data.columns).index(feature)
                    shap_vals = self.shap_values[:, feature_idx]

                    fig.add_trace(
                        {
                            "type": "violin",
                            "x": shap_vals,
                            "y": [feature] * len(shap_vals),
                            "name": feature,
                            "showlegend": False,
                        }
                    )

                fig.update_layout(
                    title="SHAP Value Distribution by Feature",
                    xaxis_title="SHAP value",
                    yaxis_title="Features",
                    height=max(400, max_features * 30),
                )

            return fig

        except Exception as e:
            logger.error(f"Error creating summary plot: {e}")
            raise

    def create_waterfall_plot(self, sample_idx: int, max_features: int = 10) -> Figure:
        """Create waterfall plot for a single prediction.

        Args:
            sample_idx: Index of the sample to explain
            max_features: Maximum number of features to show

        Returns:
            Plotly Figure object
        """
        try:
            explanation = self.explain_prediction(sample_idx)

            # Get top features by absolute SHAP value
            contributions = explanation["shap_values"]
            sorted_features = sorted(
                contributions.items(), key=lambda x: abs(x[1]), reverse=True
            )[:max_features]

            # Prepare waterfall data
            features = ["Base Value"] + [f[0] for f in sorted_features] + ["Prediction"]
            values = [explanation["base_value"]] + [f[1] for f in sorted_features]

            # Calculate cumulative values
            cumulative = [explanation["base_value"]]
            for val in values[1:-1]:
                cumulative.append(cumulative[-1] + val)
            cumulative.append(explanation["prediction"])

            # Create waterfall trace
            fig = Figure()

            # Add bars
            for i, (feature, value, _cum) in enumerate(
                zip(features, values, cumulative, strict=False)
            ):
                if i == 0:  # Base value
                    color = "gray"
                elif value > 0:
                    color = "lightgreen"
                else:
                    color = "lightcoral"

                fig.add_trace(
                    {
                        "type": "bar",
                        "x": [i],
                        "y": [value],
                        "marker": {"color": color},
                        "name": feature,
                        "showlegend": False,
                    }
                )

            # Add cumulative line
            fig.add_trace(
                {
                    "type": "scatter",
                    "x": list(range(len(features))),
                    "y": cumulative,
                    "mode": "lines+markers",
                    "line": {"color": "blue", "width": 2},
                    "name": "Cumulative",
                    "showlegend": False,
                }
            )

            fig.update_layout(
                title=f"SHAP Waterfall Plot - Sample {sample_idx}",
                xaxis_title="Features",
                yaxis_title="Value",
                xaxis={"tickvals": list(range(len(features))), "ticktext": features},
                height=500,
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating waterfall plot: {e}")
            raise

    def create_force_plot_data(self, sample_idx: int) -> dict[str, Any]:
        """Create data for force plot visualization.

        Args:
            sample_idx: Index of the sample to explain

        Returns:
            Dictionary with force plot data
        """
        try:
            explanation = self.explain_prediction(sample_idx)

            return {
                "baseValue": explanation["base_value"],
                "outValue": explanation["prediction"],
                "link": "logit",
                "features": [
                    {
                        "value": explanation["feature_values"].get(feature, 0),
                        "effect": contribution,
                        "feature": feature,
                    }
                    for feature, contribution in explanation["shap_values"].items()
                ],
            }

        except Exception as e:
            logger.error(f"Error creating force plot data: {e}")
            raise

    def get_feature_interactions(self, interaction_idx: int = 0) -> dict[str, Any]:
        """Get feature interaction values (if available).

        Args:
            interaction_idx: Index for interaction values (for multi-output models)

        Returns:
            Dictionary with interaction information
        """
        try:
            if hasattr(self.explainer, "shap_interaction_values"):
                interaction_values = self.explainer.shap_interaction_values()

                if isinstance(interaction_values, list):
                    interaction_values = interaction_values[interaction_idx]

                # Calculate mean absolute interaction effects
                mean_interactions = np.abs(interaction_values).mean(axis=0)

                # Get top interactions
                feature_names = list(self.data.columns)
                top_interactions = []

                for i in range(len(feature_names)):
                    for j in range(i + 1, len(feature_names)):
                        interaction_strength = mean_interactions[i, j]
                        if interaction_strength > 0:
                            top_interactions.append(
                                {
                                    "feature1": feature_names[i],
                                    "feature2": feature_names[j],
                                    "interaction_strength": interaction_strength,
                                }
                            )

                # Sort by interaction strength
                top_interactions.sort(
                    key=lambda x: x["interaction_strength"], reverse=True
                )

                return {
                    "interaction_matrix": interaction_values,
                    "mean_interactions": mean_interactions,
                    "top_interactions": top_interactions[:20],
                    "feature_names": feature_names,
                }
            return {
                "message": "Interaction values not available for this explainer type"
            }

        except Exception as e:
            logger.error(f"Error calculating feature interactions: {e}")
            return {"error": str(e)}

    def generate_explanation_report(
        self, sample_indices: list[int] | None = None
    ) -> dict[str, Any]:
        """Generate comprehensive explanation report.

        Args:
            sample_indices: List of sample indices to explain (random sample if None)

        Returns:
            Dictionary with comprehensive explanation report
        """
        try:
            # Select samples to explain
            if sample_indices is None:
                sample_indices = np.random.choice(
                    len(self.data), size=min(5, len(self.data)), replace=False
                ).tolist()

            # Global importance
            global_importance = self.global_importance()

            # Individual explanations
            individual_explanations = []
            for idx in sample_indices:
                individual_explanations.append(self.explain_prediction(idx))

            # Feature interactions (if available)
            interactions = self.get_feature_interactions()

            # Summary statistics
            summary_stats = {
                "total_samples": len(self.data),
                "total_features": len(self.data.columns),
                "explained_samples": len(sample_indices),
                "mean_prediction": float(np.mean(self.shap_values.sum(axis=1))),
                "std_prediction": float(np.std(self.shap_values.sum(axis=1))),
                "top_feature": (
                    global_importance.iloc[0]["feature"]
                    if len(global_importance) > 0
                    else None
                ),
                "top_feature_importance": (
                    float(global_importance.iloc[0]["importance"])
                    if len(global_importance) > 0
                    else 0.0
                ),
            }

            return {
                "global_importance": global_importance.to_dict("records"),
                "individual_explanations": individual_explanations,
                "feature_interactions": interactions,
                "summary_statistics": summary_stats,
                "model_type": self.model_type,
                "explanation_method": "SHAP",
                "timestamp": pd.Timestamp.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating explanation report: {e}")
            raise
