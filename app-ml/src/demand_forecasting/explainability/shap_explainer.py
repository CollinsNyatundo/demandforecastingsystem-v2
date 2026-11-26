"""Model explainability using SHAP for demand forecasting."""

import logging
from typing import Any

import numpy as np
import pandas as pd
import shap
from matplotlib.figure import Figure as MatplotlibFigure
from plotly.graph_objects import Figure

logger = logging.getLogger(__name__)


class ModelExplainer:
    """Generate model explanations using SHAP."""

    def __init__(self, model: object, data: pd.DataFrame, model_type: str = "tree"):
        """Initialize SHAP explainer.

        Args:
            model: Trained model to explain
            data: Reference dataset for explanation
            model_type: Type of model ('tree', 'linear', 'deep', etc.)
        """
        if not hasattr(model, "predict"):
            raise ValueError("Model must implement a 'predict' method")
        if data is None or not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Reference data must be a non-empty DataFrame")

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
            raw_shap_values = self.explainer.shap_values(data)
            self._multiclass_shap_values: np.ndarray | None = None

            # Preserve full output axis for multiclass/multi-output models
            if isinstance(raw_shap_values, list):
                stacked = np.stack(
                    [np.asarray(v, dtype=float) for v in raw_shap_values], axis=-1
                )
                self._multiclass_shap_values = stacked
                self.shap_values = stacked[:, :, 0]
            elif (
                isinstance(raw_shap_values, np.ndarray) and raw_shap_values.ndim == 3  # noqa: PLR2004
            ):
                self._multiclass_shap_values = np.asarray(raw_shap_values, dtype=float)
                self.shap_values = self._multiclass_shap_values[:, :, 0]
            else:
                self.shap_values = np.asarray(raw_shap_values, dtype=float)

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

            if top_n is not None:
                importance_df = importance_df.head(top_n)

            # Add rank
            importance_df["rank"] = range(1, len(importance_df) + 1)

            return importance_df.reset_index(drop=True)

        except Exception as e:
            logger.error(f"Error calculating global importance: {e}")
            raise

    def _resolve_multiclass_output(
        self,
        sample_idx: int,
        sample_df: pd.DataFrame,
        class_idx: int | None,
    ) -> tuple[np.ndarray, float, float | str, Any]:
        """Select matching class contributions, baseline, score, and label for multiclass models."""
        if self._multiclass_shap_values is None:
            raise ValueError("Multiclass SHAP values not available")
        predicted_label: Any = None
        resolved_idx = class_idx
        if hasattr(self.model, "predict"):
            predicted_label = self.model.predict(sample_df)[0]
            if resolved_idx is None and hasattr(self.model, "classes_"):
                classes = list(self.model.classes_)
                if predicted_label in classes:
                    resolved_idx = classes.index(predicted_label)
        if resolved_idx is None:
            resolved_idx = 0

        n_outputs = self._multiclass_shap_values.shape[2]
        if resolved_idx < 0 or resolved_idx >= n_outputs:
            raise ValueError(
                f"Class index {resolved_idx} out of range for {n_outputs} outputs"
            )

        shap_vals = np.asarray(
            self._multiclass_shap_values[sample_idx, :, resolved_idx], dtype=float
        )
        expected_arr = (
            np.asarray(self.explainer.expected_value, dtype=float).reshape(-1)
            if hasattr(self.explainer, "expected_value")
            else np.array([0.0])
        )
        base_value = (
            float(expected_arr[resolved_idx])
            if resolved_idx < expected_arr.size
            else float(expected_arr[0])
        )

        # Keep output_score strictly on the same additive scale as base_value + SHAP values
        # (works identically for probability-scale trees and raw-margin/log-odds boosters).
        output_score: float | str = float(base_value + np.sum(shap_vals))

        return shap_vals, base_value, output_score, predicted_label

    def explain_prediction(
        self,
        sample_idx: int,
        feature_names: list[str] | None = None,
        class_idx: int | None = None,
    ) -> dict[str, Any]:
        """Explain a single prediction.

        Args:
            sample_idx: Index of the sample to explain
            feature_names: Optional feature names (uses data columns if None)
            class_idx: Optional output class index for multiclass models

        Returns:
            Dictionary with prediction explanation
        """
        try:
            if sample_idx < 0 or sample_idx >= len(self.data):
                raise ValueError(f"Sample index {sample_idx} out of range")

            # Get sample and feature names
            sample = self.data.iloc[sample_idx]
            sample_df = self.data.iloc[[sample_idx]]
            if feature_names is None:
                feature_names = list(self.data.columns)

            predicted_class: Any = None
            if self._multiclass_shap_values is not None:
                (
                    shap_vals,
                    base_value,
                    prediction,
                    predicted_class,
                ) = self._resolve_multiclass_output(sample_idx, sample_df, class_idx)
            else:
                shap_vals = np.asarray(self.shap_values[sample_idx], dtype=float)
                if hasattr(self.model, "predict"):
                    prediction_raw = self.model.predict(sample_df)[0]
                    prediction = (
                        float(np.asarray(prediction_raw).flat[0])
                        if isinstance(
                            prediction_raw, (int, float, np.number, np.ndarray)
                        )
                        else str(prediction_raw)
                    )
                else:
                    prediction = "unknown"

                if hasattr(self.explainer, "expected_value"):
                    expected_arr = np.asarray(
                        self.explainer.expected_value, dtype=float
                    )
                    base_value = (
                        float(expected_arr.flat[0]) if expected_arr.size else 0.0
                    )
                else:
                    base_value = 0.0

            # Create feature contributions dictionary
            contributions = {
                name: float(val)
                for name, val in zip(feature_names, shap_vals, strict=False)
            }
            feature_importance = {
                name: float(abs(val)) for name, val in contributions.items()
            }

            # Get top contributors (positive and negative)
            sorted_contributions = sorted(
                contributions.items(), key=lambda x: abs(x[1]), reverse=True
            )
            top_positive = [(f, v) for f, v in sorted_contributions if v > 0][:5]
            top_negative = [(f, v) for f, v in sorted_contributions if v < 0][:5]

            explanation: dict[str, Any] = {
                "sample_index": sample_idx,
                "prediction": prediction,
                "base_value": base_value,
                "feature_names": feature_names,
                "shap_values": contributions,
                "feature_importance": feature_importance,
                "feature_values": dict(zip(feature_names, sample.values, strict=False)),
                "top_positive_contributors": top_positive,
                "top_negative_contributors": top_negative,
                "top_contributors": sorted_contributions[:5],
                "total_contribution": float(np.sum(shap_vals)),
            }
            if predicted_class is not None:
                explanation["predicted_class"] = (
                    predicted_class.item()
                    if isinstance(predicted_class, np.generic)
                    else predicted_class
                )
            return explanation

        except Exception as e:
            logger.error(f"Error explaining prediction: {e}")
            raise

    def create_summary_plot(
        self, plot_type: str = "bar", max_features: int = 20
    ) -> Figure | MatplotlibFigure:
        """Create SHAP summary plot using Plotly or Matplotlib.

        Args:
            plot_type: Type of plot ('bar', 'beeswarm', 'violin', 'plotly', 'matplotlib')
            max_features: Maximum number of features to show

        Returns:
            Plotly Figure or Matplotlib Figure object
        """
        valid_plot_types = {"bar", "beeswarm", "violin", "plotly", "matplotlib"}
        if plot_type not in valid_plot_types:
            raise ValueError(
                f"Invalid plot_type '{plot_type}'. Must be one of {sorted(valid_plot_types)}"
            )

        try:
            importance_df = self.global_importance(max_features)

            if plot_type == "matplotlib":
                mpl_fig = MatplotlibFigure(
                    figsize=(8, max(4, len(importance_df) * 0.4))
                )
                ax = mpl_fig.add_subplot(111)
                ax.barh(importance_df["feature"], importance_df["importance"])
                ax.set_xlabel("Mean |SHAP value|")
                ax.set_ylabel("Features")
                ax.set_title("Feature Importance (Mean |SHAP value|)")
                return mpl_fig

            if plot_type in {"bar", "plotly"}:
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

                for feature in importance_df["feature"]:
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

    def create_feature_importance_plot(
        self, max_features: int = 20, plot_type: str = "plotly"
    ) -> Figure | MatplotlibFigure:
        """Create global feature importance bar plot."""
        return self.create_summary_plot(plot_type=plot_type, max_features=max_features)

    def create_waterfall_plot(
        self, sample_idx: int, max_features: int = 10, plot_type: str = "plotly"
    ) -> Figure | MatplotlibFigure:
        """Create waterfall plot for a single prediction.

        Args:
            sample_idx: Index of the sample to explain
            max_features: Maximum number of features to show
            plot_type: Backend type ('plotly' or 'matplotlib')

        Returns:
            Plotly Figure or Matplotlib Figure object
        """
        if plot_type not in {"plotly", "matplotlib"}:
            raise ValueError(
                f"Invalid plot_type '{plot_type}'. Must be 'plotly' or 'matplotlib'"
            )

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

            if plot_type == "matplotlib":
                mpl_fig = MatplotlibFigure(figsize=(8, 5))
                ax = mpl_fig.add_subplot(111)
                ax.bar(range(len(values)), values)
                ax.set_xticks(range(len(values)))
                ax.set_xticklabels(features[: len(values)], rotation=45, ha="right")
                ax.set_title(f"SHAP Waterfall Plot - Sample {sample_idx}")
                return mpl_fig

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
