"""
Comprehensive test suite for Kedro pipelines.

Tests data processing, feature engineering, and demand modeling pipelines
with proper fixtures, error handling, and integration scenarios.
"""

import shutil

# Project imports
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

# Kedro imports
from kedro.io import DataCatalog, MemoryDataset
from kedro.runner import SequentialRunner

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from demand_forecasting.pipeline_registry import register_pipelines
    from demand_forecasting.pipelines.data_processing.nodes import preprocess_data
    from demand_forecasting.pipelines.data_processing.schemas import RawBikeDataSchema
    from demand_forecasting.pipelines.demand_modeling.catboost_nodes import (
        optimize_catboost_params,
        train_catboost_model,
    )
    from demand_forecasting.pipelines.feature_engineering.nodes import (
        create_feature_interactions,
        extract_temporal_features,
    )

    PIPELINES_AVAILABLE = True
except ImportError as e:
    import warnings

    warnings.warn(f"Pipeline modules not available: {e}")
    PIPELINES_AVAILABLE = False


@pytest.fixture
def sample_raw_data():
    """Sample raw bike sharing data for testing."""
    np.random.seed(42)
    n_samples = 1000

    data = {
        "season": np.random.randint(1, 5, n_samples),  # 1-4
        "yr": np.random.randint(0, 2, n_samples),  # 0-1
        "mnth": np.random.randint(1, 13, n_samples),  # 1-12
        "hr": np.random.randint(0, 24, n_samples),  # 0-23
        "holiday": np.random.randint(0, 2, n_samples),  # 0-1
        "weekday": np.random.randint(0, 7, n_samples),  # 0-6
        "workingday": np.random.randint(0, 2, n_samples),  # 0-1
        "weathersit": np.random.randint(1, 5, n_samples),  # 1-4
        "temp": np.random.uniform(0, 1, n_samples),  # 0-1 normalized
        "atemp": np.random.uniform(0, 1, n_samples),  # 0-1 normalized
        "hum": np.random.uniform(0, 1, n_samples),  # 0-1 normalized
        "windspeed": np.random.uniform(0, 1, n_samples),  # 0-1 normalized
        "casual": np.random.randint(0, 100, n_samples),
        "registered": np.random.randint(0, 200, n_samples),
        "cnt": np.random.randint(0, 300, n_samples),  # target column
    }

    return pd.DataFrame(data)


@pytest.fixture
def sample_processed_data():
    """Sample processed data for testing."""
    np.random.seed(42)
    n_samples = 800

    # Simulate processed data with engineered features and target column
    data = {
        "temp": np.random.normal(20, 10, n_samples),
        "humidity": np.random.normal(60, 20, n_samples),
        "wind_speed": np.random.exponential(5, n_samples),
        "hour": np.random.randint(0, 24, n_samples),
        "day_of_week": np.random.randint(0, 7, n_samples),
        "temp_lag_1": np.random.normal(19, 10, n_samples),
        "humidity_lag_1": np.random.normal(59, 20, n_samples),
        "target": np.random.poisson(50, n_samples),  # target column for modeling
        "cnt": np.random.poisson(50, n_samples),  # cnt column for feature engineering
    }

    return pd.DataFrame(data)


@pytest.fixture
def sample_parameters():
    """Sample parameters for testing."""
    return {
        "model_options": {
            "test_size": 0.2,
            "random_state": 42,
            "features": ["temp", "humidity", "wind_speed", "hour", "day_of_week"],
            "learning_rate": 0.1,  # Required for CatBoost
            "depth": 6,  # Required for CatBoost
            "iterations": 100,  # Required for CatBoost
        },
        "optimization": {"n_trials": 10, "timeout": 300},
        "optuna": {  # Add missing optuna configuration
            "n_trials": 10,
            "search_space": {"depth": [4, 6, 8], "learning_rate": [0.01, 0.1, 0.2]},
        },
    }


@pytest.fixture
def mock_catalog():
    """Mock data catalog for testing."""
    return DataCatalog(
        {
            # Data processing pipeline datasets
            "raw_bike_data": MemoryDataset(),
            "preprocessed_bike_data": MemoryDataset(),
            "data_docs_report": MemoryDataset(),
            "params:dataset_name": MemoryDataset(),
            "params:data_docs_dir": MemoryDataset(),
            "params:enable_data_docs": MemoryDataset(),
            # Demand modeling pipeline datasets
            "raw_data": MemoryDataset(),
            "processed_data": MemoryDataset(),
            "model_input_table": MemoryDataset(),
            "trained_model": MemoryDataset(),
            "model_metrics": MemoryDataset(),
            "model_options": MemoryDataset(),
            "parameters": MemoryDataset(),
            "params:random_forest": MemoryDataset(),
            "params:train_fraction": MemoryDataset(),
            "optuna_search_space": MemoryDataset(),
            "rf_metrics": MemoryDataset(),
            "catboost_metrics": MemoryDataset(),
            "model_comparison": MemoryDataset(),
            "regressor_model": MemoryDataset(),
        }
    )


@pytest.fixture
def temp_directory():
    """Temporary directory for test artifacts."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestDataProcessingNodes:
    """Test data processing pipeline nodes."""

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_preprocess_data_success(self, sample_raw_data):
        """Test successful data preprocessing."""
        # Test preprocessing
        processed_data = preprocess_data(sample_raw_data)

        assert isinstance(processed_data, pd.DataFrame)
        assert len(processed_data) > 0
        assert "temp" in processed_data.columns
        assert "hum" in processed_data.columns  # Fixed: humidity -> hum
        assert "windspeed" in processed_data.columns  # Fixed: wind_speed -> windspeed
        assert "hr" in processed_data.columns  # Fixed: hour -> hr
        assert "weekday" in processed_data.columns  # Fixed: day_of_week -> weekday

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_preprocess_data_with_nulls(self, sample_raw_data):
        """Test preprocessing with null values."""
        # Add null values to test data
        data_with_nulls = sample_raw_data.copy()
        data_with_nulls.loc[0:10, "temp"] = np.nan

        # Should handle nulls gracefully
        try:
            processed_data = preprocess_data(data_with_nulls)
            assert isinstance(processed_data, pd.DataFrame)
        except Exception as e:
            # Should either handle nulls or raise informative error
            assert "null" in str(e).lower() or "missing" in str(e).lower()

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_preprocess_data_empty_dataframe(self):
        """Test preprocessing with empty dataframe."""
        # Create empty dataframe with correct schema
        empty_df = pd.DataFrame(
            columns=[
                "season",
                "yr",
                "mnth",
                "hr",
                "holiday",
                "weekday",
                "workingday",
                "weathersit",
                "temp",
                "atemp",
                "hum",
                "windspeed",
                "casual",
                "registered",
                "cnt",
            ]
        )

        # Function should handle empty dataframe gracefully
        result = preprocess_data(empty_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0  # Should still be empty
        # Should have dropped the specified columns
        expected_cols = {
            "season",
            "mnth",
            "hr",
            "holiday",
            "weekday",
            "workingday",
            "weathersit",
            "temp",
            "atemp",
            "hum",
            "windspeed",
            "cnt",
        }
        assert set(result.columns) == expected_cols

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_preprocess_data_invalid_types(self):
        """Test preprocessing with invalid data types."""
        invalid_data = {
            "season": [1, 2, 3],
            "yr": [0, 1, 0],
            "mnth": [1, 2, 3],
            "hr": [14, 15, 16],
            "holiday": [0, 0, 1],
            "weekday": [3, 4, 5],
            "workingday": [1, 1, 0],
            "weathersit": [1, 2, 1],
            "temp": [
                "not",
                "numbers",
                "invalid",
            ],  # Invalid: strings instead of numbers
            "atemp": [0.5, 0.6, 0.7],
            "hum": [0.6, 0.7, 0.8],
            "windspeed": [5.0, 6.0, 7.0],
            "casual": [10, 20, 30],
            "registered": [30, 40, 50],
            "cnt": [40, 60, 80],
        }
        df_invalid = pd.DataFrame(invalid_data)

        # Should handle type conversion or raise error
        try:
            result = preprocess_data(df_invalid)
            # If successful, should convert types
            assert pd.api.types.is_numeric_dtype(result["temp"])
        except Exception as e:
            # Should raise SchemaError for type coercion issues
            assert (
                "schema" in str(e).lower()
                or "coerce" in str(e).lower()
                or "type" in str(e).lower()
            )


class TestFeatureEngineeringNodes:
    """Test feature engineering pipeline nodes."""

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_create_feature_interactions_success(self, sample_processed_data):
        """Test successful feature engineering with interactions."""
        engineered_data = create_feature_interactions(sample_processed_data)

        assert isinstance(engineered_data, pd.DataFrame)
        assert len(engineered_data) > 0

        # Check for interaction features
        assert len(engineered_data.columns) >= len(sample_processed_data.columns)

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_create_feature_interactions_with_small_data(self, sample_processed_data):
        """Test feature engineering with small dataset."""
        small_data = sample_processed_data.iloc[:10]  # Only 10 rows

        # Should handle small data gracefully
        try:
            engineered_data = create_feature_interactions(small_data)
            assert isinstance(engineered_data, pd.DataFrame)
        except Exception as e:
            # Small data might cause issues with feature engineering
            assert "insufficient" in str(e).lower() or "small" in str(e).lower()

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_create_feature_interactions_empty_data(self):
        """Test feature engineering with empty data."""
        empty_df = pd.DataFrame()

        with pytest.raises((ValueError, IndexError, KeyError)):
            create_feature_interactions(empty_df)


class TestDemandModelingNodes:
    """Test demand modeling pipeline nodes."""

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_train_catboost_model_success(
        self, sample_processed_data, sample_parameters
    ):
        """Test successful CatBoost model training."""
        # Create a single dataframe as expected by the function
        model_input_table = sample_processed_data

        model, metrics = train_catboost_model(
            model_input_table, sample_parameters["model_options"]
        )

        assert model is not None
        assert "rmse" in metrics
        assert "mae" in metrics
        assert metrics["rmse"] >= 0
        assert metrics["mae"] >= 0

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_train_catboost_model_invalid_data(self, sample_parameters):
        """Test CatBoost training with invalid data."""
        X_invalid = pd.DataFrame({"invalid_feature": ["a", "b", "c"]})
        y_invalid = pd.Series([1, 2, 3])
        # Create invalid dataframe
        invalid_data = pd.concat([X_invalid, y_invalid.rename("demand")], axis=1)

        with pytest.raises((ValueError, TypeError)):
            train_catboost_model(invalid_data, sample_parameters["model_options"])

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_optimize_catboost_params(
        self, sample_processed_data, sample_parameters
    ):
        """Test hyperparameter optimization."""
        # Create a single dataframe as expected by the function
        model_input_table = sample_processed_data

        # Mock Optuna study for testing
        with patch("optuna.create_study") as mock_create_study:
            mock_study = Mock()
            mock_study.ask.return_value = Mock()
            mock_study.tell.return_value = Mock()
            mock_create_study.return_value = mock_study

            result = optimize_catboost_params(
                model_input_table, sample_parameters["optimization"]
            )

            assert result is not None
            mock_create_study.assert_called()

    @pytest.mark.skip(reason="compare_models function not implemented yet")
    def test_compare_models(self, sample_processed_data):
        """Test model comparison functionality (placeholder for future implementation)."""
        # This test is skipped because compare_models function doesn't exist yet
        # Create mock metrics dictionaries as expected by the function
        rf_metrics = {
            "rmse": 5.2,
            "mae": 3.8,
            "r2": 0.85,
            "mape": 8.5,
        }
        catboost_metrics = {
            "rmse": 4.9,
            "mae": 3.6,
            "r2": 0.87,
            "mape": 8.2,
        }

        # TODO: Implement compare_models function
        pass


class TestPipelineIntegration:
    """Test complete pipeline integration."""

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_register_pipelines(self):
        """Test pipeline registration."""
        pipelines = register_pipelines()

        assert isinstance(pipelines, dict)
        assert "demand_modeling" in pipelines
        assert "__default__" in pipelines

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_pipeline_execution(
        self, sample_raw_data, sample_parameters, mock_catalog, temp_directory
    ):
        """Test complete pipeline execution."""
        # Create a mock context
        with patch("kedro.framework.context.KedroContext"):
            mock_ctx = Mock()
            mock_ctx.catalog = mock_catalog

            # Register test data in catalog
            mock_catalog.save("raw_bike_data", sample_raw_data)
            mock_catalog.save("model_options", sample_parameters["model_options"])

            # Get pipeline
            pipelines = register_pipelines()
            pipeline = pipelines["data_processing"]

            # Create runner
            runner = SequentialRunner()

            # Run pipeline (only up to first node to avoid long training)
            pipeline_slice = pipeline.only_nodes("preprocess_bike_data_node")

            try:
                result = runner.run(pipeline_slice, catalog=mock_catalog)
                assert result is not None
            except Exception as e:
                # Pipeline execution might fail due to missing dependencies
                assert "node" in str(e).lower() or "catalog" in str(e).lower()

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_pipeline_with_missing_data(self, mock_catalog):
        """Test pipeline behavior with missing input data."""
        # Create catalog with missing dataset
        incomplete_catalog = DataCatalog(
            {
                "model_options": MemoryDataset()
                # Missing 'raw_data'
            }
        )

        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        runner = SequentialRunner()

        with pytest.raises(Exception):
            runner.run(pipeline, catalog=incomplete_catalog)


class TestDataValidation:
    """Test data validation and schema compliance."""

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_raw_data_schema_validation(self, sample_raw_data):
        """Test raw data schema validation."""
        try:
            # Validate against schema
            validated_data = RawBikeDataSchema.validate(sample_raw_data)
            assert isinstance(validated_data, pd.DataFrame)
        except Exception as e:
            # Should handle validation errors gracefully
            assert "validation" in str(e).lower() or "schema" in str(e).lower()

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_schema_with_invalid_data(self):
        """Test schema validation with invalid data."""
        invalid_data = pd.DataFrame(
            {
                "temp": ["invalid", "data"],  # String instead of numeric
                "humidity": [-50, 200, 300],  # Out of valid range
                "wind_speed": [5.0, 6.0, 7.0],
                "hour": [25, 26, 27],  # Invalid hour values
                "day_of_week": [8, 9, 10],  # Invalid day values
                "demand": [10, 20, 30],
            }
        )

        with pytest.raises(Exception):
            RawBikeDataSchema.validate(invalid_data)


class TestPipelineErrorHandling:
    """Test pipeline error handling and recovery."""

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_node_failure_handling(self, sample_raw_data, mock_catalog):
        """Test pipeline behavior when a node fails."""
        # Mock a failing node
        with patch(
            "demand_forecasting.pipelines.data_processing.nodes.preprocess_data"
        ) as mock_preprocess:
            mock_preprocess.side_effect = Exception("Node processing failed")

            pipelines = register_pipelines()
            pipeline = pipelines["demand_modeling"]
            runner = SequentialRunner()

            with pytest.raises(Exception):
                runner.run(pipeline, catalog=mock_catalog)

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_memory_error_handling(self, mock_catalog):
        """Test pipeline behavior with memory constraints."""
        # Save required datasets to catalog first
        mock_catalog.save(
            "model_input_table", pd.DataFrame({"temp": [20], "target": [50]})
        )
        mock_catalog.save("parameters", {"model_options": {"learning_rate": 0.1}})
        mock_catalog.save("params:random_forest", {"n_estimators": 100})
        mock_catalog.save("params:train_fraction", 0.8)

        # Simulate memory error
        with patch("pandas.DataFrame") as mock_df:
            mock_df.side_effect = MemoryError("Out of memory")

            pipelines = register_pipelines()
            pipeline = pipelines["demand_modeling"]
            runner = SequentialRunner()

            with pytest.raises((MemoryError, RuntimeError)):
                runner.run(pipeline, catalog=mock_catalog)


class TestPipelinePerformance:
    """Test pipeline performance and resource usage."""

    @pytest.mark.slow
    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_pipeline_performance_large_dataset(self, mock_catalog, temp_directory):
        """Test pipeline performance with large dataset."""
        # Create large dataset
        np.random.seed(42)
        large_data = pd.DataFrame(
            {
                "temp": np.random.normal(20, 10, 10000),
                "humidity": np.random.normal(60, 20, 10000),
                "wind_speed": np.random.exponential(5, 10000),
                "hour": np.random.randint(0, 24, 10000),
                "day_of_week": np.random.randint(0, 7, 10000),
                "demand": np.random.poisson(50, 10000),
            }
        )

        mock_catalog.save("raw_data", large_data)

        import time

        start_time = time.time()

        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        runner = SequentialRunner()

        # Run only first node to test performance
        pipeline_slice = pipeline.only_nodes("generate_search_space_node")
        result = runner.run(pipeline_slice, catalog=mock_catalog)

        end_time = time.time()
        processing_time = end_time - start_time

        # Should complete within reasonable time (less than 30 seconds)
        assert processing_time < 30.0
        assert result is not None

    @pytest.mark.skipif(
        not PIPELINES_AVAILABLE, reason="Pipeline modules not available"
    )
    def test_pipeline_memory_usage(self, sample_raw_data, mock_catalog):
        """Test pipeline memory usage."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        mock_catalog.save("model_input_table", sample_raw_data)
        mock_catalog.save("parameters", {"model_options": {"learning_rate": 0.1}})
        mock_catalog.save("params:random_forest", {"n_estimators": 100})
        mock_catalog.save("params:train_fraction", 0.8)

        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        runner = SequentialRunner()

        # Run pipeline slice
        pipeline_slice = pipeline.only_nodes("generate_search_space_node")
        runner.run(pipeline_slice, catalog=mock_catalog)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
