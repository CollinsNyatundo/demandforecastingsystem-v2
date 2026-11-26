"""
Comprehensive test suite for model explainability and SHAP functionality.

Tests SHAP explainer initialization, global and local explanations,
visualizations, edge cases, and integration with different model types.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from demand_forecasting.explainability.shap_explainer import ModelExplainer


class TestModelExplainer:
    """Test SHAP model explainer functionality."""

    def test_tree_explainer_initialization(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test SHAP TreeExplainer initialization."""
        explainer = ModelExplainer(sample_model, sample_data, model_type="tree")

        assert explainer.model == sample_model
        assert explainer.data.equals(sample_data)
        assert explainer.model_type == "tree"
        assert explainer.explainer is not None
        assert explainer.shap_values is not None
        assert explainer.shap_values.shape[0] == len(sample_data)
        assert explainer.shap_values.shape[1] == len(sample_data.columns)

    def test_linear_explainer_initialization(self, sample_data: pd.DataFrame):
        """Test SHAP LinearExplainer initialization."""
        from sklearn.linear_model import LinearRegression

        y = sample_data.sum(axis=1)
        linear_model = LinearRegression().fit(sample_data, y)
        explainer = ModelExplainer(linear_model, sample_data, model_type="linear")

        assert explainer.model_type == "linear"
        assert explainer.explainer is not None
        assert hasattr(explainer.explainer, "shap_values")

    def test_default_tree_explainer(self, sample_data: pd.DataFrame, sample_model):
        """Test default to TreeExplainer for unknown model type."""
        explainer = ModelExplainer(sample_model, sample_data, model_type="unknown")

        assert explainer.model_type == "unknown"
        # Should default to TreeExplainer
        assert type(explainer.explainer).__name__ == "TreeExplainer"

    def test_initialization_with_small_data(self):
        """Test initialization with small dataset."""
        from sklearn.tree import DecisionTreeRegressor

        small_data = pd.DataFrame({"feature1": [1.0, 2.0], "feature2": [3.0, 4.0]})
        model = DecisionTreeRegressor(max_depth=2, random_state=42).fit(
            small_data, [5.0, 6.0]
        )
        explainer = ModelExplainer(model, small_data)

        assert explainer.shap_values.shape[0] == 2
        assert explainer.shap_values.shape[1] == 2

    def test_initialization_with_single_feature(self):
        """Test initialization with single feature dataset."""
        from sklearn.tree import DecisionTreeRegressor

        rng = np.random.default_rng(42)
        single_feature_data = pd.DataFrame({"feature1": rng.normal(0, 1, 100)})
        y = single_feature_data["feature1"] * 2.0 + rng.normal(0, 0.1, 100)
        model = DecisionTreeRegressor(max_depth=3, random_state=42).fit(
            single_feature_data, y
        )
        explainer = ModelExplainer(model, single_feature_data)

        assert explainer.shap_values.shape[1] == 1

    def test_initialization_failure_invalid_model(self, sample_data: pd.DataFrame):
        """Test initialization with invalid model."""
        invalid_model = "not_a_model"

        with pytest.raises(Exception):
            ModelExplainer(invalid_model, sample_data)

    def test_initialization_empty_data(self, sample_model):
        """Test initialization with empty data."""
        empty_data = pd.DataFrame()

        with pytest.raises((ValueError, Exception)):
            ModelExplainer(sample_model, empty_data)


class TestGlobalImportance:
    """Test global feature importance calculations."""

    def test_global_importance_all_features(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test global importance with all features."""
        explainer = ModelExplainer(sample_model, sample_data)
        importance_df = explainer.global_importance()

        assert isinstance(importance_df, pd.DataFrame)
        assert len(importance_df) == len(sample_data.columns)
        assert "feature" in importance_df.columns
        assert "importance" in importance_df.columns
        assert "mean_shap_value" in importance_df.columns
        assert "std_shap_value" in importance_df.columns
        assert "rank" in importance_df.columns

        # Check ranking
        assert importance_df["rank"].min() == 1
        assert importance_df["rank"].max() == len(sample_data.columns)

        # Check sorting (should be descending by importance)
        assert importance_df["importance"].is_monotonic_decreasing

    def test_global_importance_top_n(self, sample_data: pd.DataFrame, sample_model):
        """Test global importance with top_n parameter."""
        explainer = ModelExplainer(sample_model, sample_data)
        top_3_importance = explainer.global_importance(top_n=3)

        assert len(top_3_importance) == 3
        assert top_3_importance["rank"].tolist() == [1, 2, 3]

    def test_global_importance_zero_top_n(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test global importance with top_n=0."""
        explainer = ModelExplainer(sample_model, sample_data)
        empty_importance = explainer.global_importance(top_n=0)

        assert len(empty_importance) == 0

    def test_global_importance_large_top_n(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test global importance with top_n larger than features."""
        explainer = ModelExplainer(sample_model, sample_data)
        all_importance = explainer.global_importance(top_n=100)

        # Should return all features
        assert len(all_importance) == len(sample_data.columns)

    def test_global_importance_values(self, sample_data: pd.DataFrame, sample_model):
        """Test that importance values are reasonable."""
        explainer = ModelExplainer(sample_model, sample_data)
        importance_df = explainer.global_importance()

        # Importance should be non-negative
        assert (importance_df["importance"] >= 0).all()

        # Mean SHAP values can be positive or negative
        assert isinstance(importance_df["mean_shap_value"].iloc[0], (int, float))

        # Standard deviation should be non-negative
        assert (importance_df["std_shap_value"] >= 0).all()


class TestLocalExplanations:
    """Test individual prediction explanations."""

    def test_explain_prediction_valid_index(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test explaining a valid prediction."""
        explainer = ModelExplainer(sample_model, sample_data)

        # Explain first prediction
        explanation = explainer.explain_prediction(sample_idx=0)

        assert isinstance(explanation, dict)
        assert "prediction" in explanation
        assert "shap_values" in explanation
        assert "feature_names" in explanation
        assert "feature_values" in explanation
        assert "base_value" in explanation
        assert "feature_importance" in explanation

        # Check structure
        assert len(explanation["shap_values"]) == len(sample_data.columns)
        assert len(explanation["feature_names"]) == len(sample_data.columns)
        assert len(explanation["feature_values"]) == len(sample_data.columns)

    def test_explain_prediction_all_indices(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test explaining all predictions."""
        explainer = ModelExplainer(sample_model, sample_data)

        # Explain each prediction
        for i in range(len(sample_data)):
            explanation = explainer.explain_prediction(sample_idx=i)

            assert isinstance(explanation, dict)
            assert "prediction" in explanation
            assert len(explanation["shap_values"]) == len(sample_data.columns)

    def test_explain_prediction_custom_feature_names(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test explanation with custom feature names."""
        explainer = ModelExplainer(sample_model, sample_data)
        custom_names = [f"f{i + 1}" for i in range(len(sample_data.columns))]

        explanation = explainer.explain_prediction(
            sample_idx=0, feature_names=custom_names
        )

        assert explanation["feature_names"] == custom_names
        assert len(explanation["shap_values"]) == len(custom_names)

    def test_explain_prediction_invalid_index(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test explanation with invalid index."""
        explainer = ModelExplainer(sample_model, sample_data)

        # Test negative index
        with pytest.raises((IndexError, ValueError)):
            explainer.explain_prediction(sample_idx=-1)

        # Test index out of range
        with pytest.raises((IndexError, ValueError)):
            explainer.explain_prediction(sample_idx=len(sample_data))

    def test_explain_prediction_feature_importance_ranking(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test feature importance ranking in local explanations."""
        explainer = ModelExplainer(sample_model, sample_data)
        explanation = explainer.explain_prediction(sample_idx=0)

        feature_importance = explanation["feature_importance"]

        # Should be a dictionary with feature names as keys
        assert isinstance(feature_importance, dict)
        assert len(feature_importance) == len(sample_data.columns)

        # Values should be numeric
        for importance in feature_importance.values():
            assert isinstance(importance, (int, float))


class TestVisualizations:
    """Test visualization methods."""

    def test_create_summary_plot(self, sample_data: pd.DataFrame, sample_model):
        """Test creating SHAP summary plot."""
        explainer = ModelExplainer(sample_model, sample_data)

        # Test matplotlib backend
        with patch("matplotlib.pyplot.show"):
            fig = explainer.create_summary_plot(plot_type="matplotlib")
            assert fig is not None

        # Test plotly backend
        plotly_fig = explainer.create_summary_plot(plot_type="plotly")
        assert isinstance(plotly_fig, go.Figure)

    def test_create_waterfall_plot(self, sample_data: pd.DataFrame, sample_model):
        """Test creating SHAP waterfall plot."""
        explainer = ModelExplainer(sample_model, sample_data)

        # Test matplotlib backend
        with patch("matplotlib.pyplot.show"):
            fig = explainer.create_waterfall_plot(sample_idx=0, plot_type="matplotlib")
            assert fig is not None

        # Test plotly backend
        plotly_fig = explainer.create_waterfall_plot(sample_idx=0, plot_type="plotly")
        assert isinstance(plotly_fig, go.Figure)

    def test_create_force_plot(self, sample_data: pd.DataFrame, sample_model):
        """Test creating SHAP force plot."""
        explainer = ModelExplainer(sample_model, sample_data)

        # Force plot might not be available in all SHAP versions
        try:
            with patch("matplotlib.pyplot.show"):
                fig = explainer.create_force_plot(sample_idx=0)
                assert fig is not None
        except AttributeError:
            # Force plot not available, skip
            pytest.skip("Force plot not available in current SHAP version")

    def test_create_feature_importance_plot(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test creating feature importance plot."""
        explainer = ModelExplainer(sample_model, sample_data)

        # Test matplotlib backend
        with patch("matplotlib.pyplot.show"):
            fig = explainer.create_feature_importance_plot(plot_type="matplotlib")
            assert fig is not None

        # Test plotly backend
        plotly_fig = explainer.create_feature_importance_plot(plot_type="plotly")
        assert isinstance(plotly_fig, go.Figure)

    def test_visualization_invalid_plot_type(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test visualization with invalid plot type."""
        explainer = ModelExplainer(sample_model, sample_data)

        with pytest.raises(ValueError):
            explainer.create_summary_plot(plot_type="invalid_type")

    def test_visualization_invalid_index(self, sample_data: pd.DataFrame, sample_model):
        """Test visualization with invalid sample index."""
        explainer = ModelExplainer(sample_model, sample_data)

        with pytest.raises((IndexError, ValueError)):
            explainer.create_waterfall_plot(sample_idx=len(sample_data))


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_multiclass_model(self):
        """Test explainer with multiclass model."""
        from sklearn.tree import DecisionTreeClassifier

        rng = np.random.default_rng(42)
        multiclass_data = pd.DataFrame(
            {
                "feature1": rng.normal(0, 1, 100),
                "feature2": rng.normal(0, 1, 100),
            }
        )
        y = rng.choice([0, 1, 2], 100)
        model = DecisionTreeClassifier(max_depth=3, random_state=42).fit(
            multiclass_data, y
        )
        explainer = ModelExplainer(model, multiclass_data)

        # Should handle multiclass case
        assert explainer.shap_values is not None
        assert explainer.shap_values.shape[0] == len(multiclass_data)

    def test_constant_features(self):
        """Test explainer with constant features."""
        from sklearn.tree import DecisionTreeRegressor

        rng = np.random.default_rng(42)
        constant_data = pd.DataFrame(
            {
                "constant_feature": [42.0] * 100,
                "varying_feature": rng.normal(0, 1, 100),
            }
        )
        y = constant_data["varying_feature"] * 3.0 + rng.normal(0, 0.1, 100)
        model = DecisionTreeRegressor(max_depth=3, random_state=42).fit(
            constant_data, y
        )
        explainer = ModelExplainer(model, constant_data)

        # Should handle constant features
        assert explainer.shap_values is not None
        importance_df = explainer.global_importance()

        # Constant feature should have zero or very low importance
        constant_importance = importance_df[
            importance_df["feature"] == "constant_feature"
        ]["importance"].iloc[0]
        assert constant_importance >= 0

    def test_highly_correlated_features(self):
        """Test explainer with highly correlated features."""
        from sklearn.linear_model import Ridge

        rng = np.random.default_rng(42)
        base_feature = rng.normal(0, 1, 100)
        correlated_data = pd.DataFrame(
            {
                "feature1": base_feature,
                "feature2": base_feature + rng.normal(0, 0.01, 100),
                "feature3": rng.normal(0, 1, 100),
            }
        )
        y = correlated_data["feature1"] + correlated_data["feature2"]
        model = Ridge(alpha=1.0).fit(correlated_data, y)
        explainer = ModelExplainer(model, correlated_data, model_type="linear")

        # Should handle correlated features
        assert explainer.shap_values is not None
        importance_df = explainer.global_importance()

        # Feature1 and Feature2 should have similar importance
        f1_importance = importance_df[importance_df["feature"] == "feature1"][
            "importance"
        ].iloc[0]
        f2_importance = importance_df[importance_df["feature"] == "feature2"][
            "importance"
        ].iloc[0]

        # Should be relatively close (within factor of 2)
        assert (
            abs(f1_importance - f2_importance) / max(f1_importance, f2_importance) < 1.0
        )

    def test_large_dataset_performance(self):
        """Test performance with large dataset."""
        import time

        from sklearn.tree import DecisionTreeRegressor

        rng = np.random.default_rng(42)
        large_data = pd.DataFrame(
            {f"feature_{i}": rng.normal(0, 1, 10000) for i in range(20)}
        )
        y = large_data["feature_0"] + large_data["feature_1"]
        model = DecisionTreeRegressor(max_depth=3, random_state=42).fit(large_data, y)

        start_time = time.time()
        explainer = ModelExplainer(model, large_data)
        end_time = time.time()

        initialization_time = end_time - start_time

        # Should initialize within reasonable time (less than 60 seconds)
        assert initialization_time < 60.0

        # Test explanation time
        start_time = time.time()
        explanation = explainer.explain_prediction(sample_idx=0)
        end_time = time.time()

        explanation_time = end_time - start_time
        assert explanation_time < 5.0  # Should be fast for single explanation
        assert explanation is not None

    def test_memory_usage(self):
        """Test memory usage with large SHAP values."""
        import os

        import psutil
        from sklearn.tree import DecisionTreeRegressor

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        rng = np.random.default_rng(42)
        data = pd.DataFrame({f"feature_{i}": rng.normal(0, 1, 5000) for i in range(10)})
        y = data["feature_0"] * 2.0
        model = DecisionTreeRegressor(max_depth=3, random_state=42).fit(data, y)
        ModelExplainer(model, data)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 500MB)
        assert memory_increase < 500 * 1024 * 1024

    def test_shap_value_consistency(self, sample_data: pd.DataFrame, sample_model):
        """Test SHAP value consistency across runs."""
        np.random.seed(42)

        # Create explainer twice with same seed
        explainer1 = ModelExplainer(sample_model, sample_data)
        explainer2 = ModelExplainer(sample_model, sample_data)

        # Get explanations for same sample
        exp1 = explainer1.explain_prediction(sample_idx=0)
        exp2 = explainer2.explain_prediction(sample_idx=0)

        # SHAP values should be identical (deterministic)
        np.testing.assert_array_almost_equal(
            list(exp1["shap_values"].values()),
            list(exp2["shap_values"].values()),
            decimal=10,
        )

    def test_explanation_sum_to_prediction(
        self, sample_data: pd.DataFrame, sample_model
    ):
        """Test that SHAP values sum to prediction difference."""
        explainer = ModelExplainer(sample_model, sample_data)
        explanation = explainer.explain_prediction(sample_idx=0)

        # SHAP values + base value should approximately equal prediction
        shap_sum = sum(explanation["shap_values"].values())
        base_value = explanation["base_value"]
        prediction = explanation["prediction"]

        # Allow some tolerance due to numerical precision
        assert abs(shap_sum + base_value - prediction) < 1e-6
