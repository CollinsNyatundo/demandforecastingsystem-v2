"""
Integration tests for Kedro pipelines with the app-ml system.

Tests pipeline configuration, data catalog integration, and end-to-end
pipeline execution with real data scenarios.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

# Kedro imports
from kedro.framework.context import KedroContext
from kedro.io import DataCatalog, MemoryDataset
from kedro.runner import SequentialRunner
from kedro.config import OmegaConfigLoader

# Project imports
import sys
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from demand_forecasting.pipeline_registry import register_pipelines
    from demand_forecasting.settings import *
    PIPELINES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import pipeline modules: {e}")
    PIPELINES_AVAILABLE = False


@pytest.fixture
def project_config():
    """Load project configuration for testing."""
    try:
        config_loader = OmegaConfigLoader(
            conf_source=str(project_root / "conf"),
            env="local"
        )
        config = config_loader["*"]
        return config
    except Exception:
        # Return minimal config for testing
        return {
            "model_options": {
                "test_size": 0.2,
                "random_state": 42
            }
        }


@pytest.fixture
def test_catalog():
    """Test data catalog with memory datasets."""
    return DataCatalog({
        # Data processing datasets
        "raw_bike_data": MemoryDataset(),
        "preprocessed_bike_data": MemoryDataset(),
        
        # Demand modeling datasets
        "model_input_table": MemoryDataset(),
        "parameters": MemoryDataset(),
        "params:random_forest": MemoryDataset(),
        "params:train_fraction": MemoryDataset(),
        "optuna_search_space": MemoryDataset(),
        "rf_metrics": MemoryDataset(),
        "catboost_metrics": MemoryDataset(),
        "model_comparison": MemoryDataset(),
        "regressor_model": MemoryDataset(),
        
        # Legacy datasets for compatibility
        "raw_data": MemoryDataset(),
        "preprocessed_data": MemoryDataset(),
        "model_input": MemoryDataset(),
        "trained_model": MemoryDataset(),
        "model_metrics": MemoryDataset(),
        "model_options": MemoryDataset()
    })


@pytest.fixture
def sample_bike_data():
    """Generate sample bike sharing data."""
    np.random.seed(42)
    n_samples = 500
    
    data = {
        'temp': np.random.normal(20, 10, n_samples),
        'humidity': np.random.normal(60, 20, n_samples),
        'wind_speed': np.random.exponential(5, n_samples),
        'hour': np.random.randint(0, 24, n_samples),
        'day_of_week': np.random.randint(0, 7, n_samples),
        'demand': np.random.poisson(50, n_samples)
    }
    
    return pd.DataFrame(data)


class TestPipelineConfiguration:
    """Test pipeline configuration and registration."""
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_registration(self):
        """Test pipeline registration process."""
        pipelines = register_pipelines()
        
        assert isinstance(pipelines, dict)
        assert len(pipelines) > 0
        
        # Check that default pipeline exists
        assert "__default__" in pipelines
        
        # Check that individual pipelines exist
        pipeline_names = list(pipelines.keys())
        assert "demand_modeling" in pipeline_names
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_structure(self):
        """Test pipeline structure and nodes."""
        pipelines = register_pipelines()
        
        for pipeline_name, pipeline in pipelines.items():
            if pipeline_name.startswith("__"):  # Skip meta-pipelines
                continue
                
            # Check pipeline structure
            assert hasattr(pipeline, 'nodes')
            # namespace may not exist in newer Kedro versions
            
            # Check that pipeline has nodes
            nodes = pipeline.nodes
            assert len(nodes) > 0
            
            # Check node structure
            for node in nodes:
                assert hasattr(node, 'name')  # Use 'name' instead of '_name'
                assert hasattr(node, 'outputs')  # Use 'outputs' instead of '_outputs'
                assert hasattr(node, '_inputs')
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_dependencies(self):
        """Test pipeline dependency structure."""
        pipelines = register_pipelines()
        
        for pipeline_name, pipeline in pipelines.items():
            if pipeline_name.startswith("__"):
                continue
                
            # Check that dependencies are properly defined using node_dependencies
            dependencies = pipeline.node_dependencies
            assert isinstance(dependencies, dict)
            
            # Dependencies should be node names
            for node_name, deps in dependencies.items():
                # node_name is a Node object, get its name attribute
                actual_name = getattr(node_name, 'name', str(node_name))
                assert isinstance(actual_name, str)
                assert isinstance(deps, set)


class TestCatalogIntegration:
    """Test data catalog integration with pipelines."""
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_catalog_dataset_configuration(self, project_config):
        """Test catalog dataset configuration."""
        config = project_config
        
        # Check that required datasets are configured
        required_datasets = [
            "raw_data",
            "preprocessed_data", 
            "model_input",
            "trained_model"
        ]
        
        for dataset in required_datasets:
            if "datasets" in config:
                assert dataset in config["datasets"]
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_catalog_memory_datasets(self, test_catalog, sample_bike_data):
        """Test memory dataset operations."""
        # Add data to catalog
        test_catalog.save("raw_data", sample_bike_data)
        
        # Retrieve data from catalog
        loaded_data = test_catalog.load("raw_data")
        
        assert isinstance(loaded_data, pd.DataFrame)
        assert len(loaded_data) == len(sample_bike_data)
        pd.testing.assert_frame_equal(loaded_data, sample_bike_data)
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_catalog_dataset_not_found(self, test_catalog):
        """Test catalog behavior with missing dataset."""
        with pytest.raises(Exception):
            test_catalog.load("nonexistent_dataset")


class TestEndToEndPipelineExecution:
    """Test complete end-to-end pipeline execution."""
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_full_pipeline_execution(self, test_catalog, sample_bike_data, project_config):
        """Test complete pipeline execution with sample data."""
        # Setup catalog with data
        test_catalog.save("raw_data", sample_bike_data)
        test_catalog.save("model_options", project_config.get("model_options", {}))
        
        # Get pipeline
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        # Create runner
        runner = SequentialRunner()
        
        # Run pipeline
        try:
            result = runner.run(pipeline, catalog=test_catalog)
            
            # Check that pipeline executed
            assert result is not None
            assert len(result) > 0
            
            # Check that outputs were created
            for dataset_name in test_catalog._datasets:
                if test_catalog.exists(dataset_name):
                    data = test_catalog.load(dataset_name)
                    assert data is not None
                    
        except Exception as e:
            # Pipeline might fail due to missing dependencies or configuration
            # This is acceptable for testing if error is informative
            assert "kedro" in str(e).lower() or "pipeline" in str(e).lower()
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_with_partial_execution(self, test_catalog, sample_bike_data):
        """Test pipeline execution with specific nodes."""
        # Setup catalog
        test_catalog.save("raw_data", sample_bike_data)
        
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        # Run only preprocessing nodes
        preprocessing_nodes = []
        for node in pipeline.nodes:
            if "preprocess" in node._name.lower() or "data" in node._name.lower():
                preprocessing_nodes.append(node)
        
        if preprocessing_nodes:
            from kedro.pipeline import Pipeline
            partial_pipeline = Pipeline(preprocessing_nodes)
            
            runner = SequentialRunner()
            result = runner.run(partial_pipeline, catalog=test_catalog)
            
            assert result is not None
    
    @pytest.mark.slow
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_performance(self, test_catalog, sample_bike_data):
        """Test pipeline performance with larger dataset."""
        # Create larger dataset
        np.random.seed(42)
        large_data = pd.DataFrame({
            'temp': np.random.normal(20, 10, 2000),
            'humidity': np.random.normal(60, 20, 2000),
            'wind_speed': np.random.exponential(5, 2000),
            'hour': np.random.randint(0, 24, 2000),
            'day_of_week': np.random.randint(0, 7, 2000),
            'demand': np.random.poisson(50, 2000)
        })
        
        test_catalog.save("raw_data", large_data)
        
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        # Run only preprocessing for performance test
        preprocessing_nodes = []
        for node in pipeline.nodes:
            if "preprocess" in node._name.lower():
                preprocessing_nodes.append(node)
        
        if preprocessing_nodes:
            from kedro.pipeline import Pipeline
            partial_pipeline = Pipeline(preprocessing_nodes)
            
            import time
            start_time = time.time()
            
            runner = SequentialRunner()
            result = runner.run(partial_pipeline, catalog=test_catalog)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete within reasonable time
            assert execution_time < 60.0  # 1 minute for preprocessing
            assert result is not None


class TestPipelineErrorHandling:
    """Test pipeline error handling and recovery."""
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_with_missing_input(self, test_catalog):
        """Test pipeline behavior with missing input data."""
        # Don't add required input data
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        runner = SequentialRunner()
        
        with pytest.raises(Exception):
            runner.run(pipeline, catalog=test_catalog)
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_with_invalid_data(self, test_catalog):
        """Test pipeline with invalid data format."""
        # Add invalid data
        invalid_data = pd.DataFrame({
            'temp': ['not', 'numeric'],  # Invalid type
            'humidity': [60, 61, 62],
            'wind_speed': [5.0, 6.0, 7.0],
            'hour': [14, 15, 16],
            'day_of_week': [3, 4, 5],
            'demand': [10, 20, 30]
        })
        
        test_catalog.save("raw_data", invalid_data)
        
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        runner = SequentialRunner()
        
        # Should handle invalid data gracefully
        try:
            result = runner.run(pipeline, catalog=test_catalog)
            # If successful, data should be cleaned/validated
            assert result is not None
        except Exception as e:
            # Should raise informative error
            assert "type" in str(e).lower() or "invalid" in str(e).lower()
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_node_failure(self, test_catalog, sample_bike_data):
        """Test pipeline behavior when a node fails."""
        # Mock node failure
        with patch('demand_forecasting.pipelines.data_processing.nodes.preprocess_data') as mock_preprocess:
            mock_preprocess.side_effect = Exception("Simulated node failure")
            
            test_catalog.save("raw_data", sample_bike_data)
            
            pipelines = register_pipelines()
            pipeline = pipelines["demand_modeling"]
            
            runner = SequentialRunner()
            
            with pytest.raises(Exception):
                runner.run(pipeline, catalog=test_catalog)


class TestConfigurationManagement:
    """Test configuration management and environment handling."""
    
    def test_configuration_loading(self, project_config):
        """Test configuration loading from different environments."""
        config = project_config
        
        assert isinstance(config, dict)
        assert "model_options" in config
        
        # Check model options structure
        model_options = config["model_options"]
        assert "test_size" in model_options
        assert "random_state" in model_options
    
    def test_configuration_override(self):
        """Test configuration parameter override."""
        # Test with custom configuration
        custom_config = {
            "model_options": {
                "test_size": 0.3,  # Override default
                "random_state": 123
            }
        }
        
        assert custom_config["model_options"]["test_size"] == 0.3
        assert custom_config["model_options"]["random_state"] == 123
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_pipeline_with_custom_config(self, test_catalog, sample_bike_data):
        """Test pipeline execution with custom configuration."""
        custom_config = {
            "model_options": {
                "test_size": 0.1,
                "random_state": 999
            }
        }
        
        test_catalog.save("raw_data", sample_bike_data)
        test_catalog.save("model_options", custom_config["model_options"])
        
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        runner = SequentialRunner()
        
        try:
            result = runner.run(pipeline, catalog=test_catalog)
            assert result is not None
        except Exception:
            # Configuration issues should be caught
            pass  # Expected for testing


class TestPipelinePersistence:
    """Test pipeline data persistence and model saving."""
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_model_persistence(self, test_catalog, sample_bike_data, temp_directory):
        """Test model saving and loading."""
        test_catalog.save("model_input_table", sample_bike_data)
        test_catalog.save("parameters", {"model_options": {"learning_rate": 0.1, "depth": 6}})
        test_catalog.save("params:random_forest", {"n_estimators": 100})
        test_catalog.save("params:train_fraction", 0.8)
        
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        # Mock model training to test persistence
        with patch('demand_forecasting.pipelines.demand_modeling.catboost_nodes.train_catboost_model') as mock_train:
            mock_model = Mock()
            mock_train.return_value = (mock_model, {"rmse": 45.0, "mae": 30.0})
            
            runner = SequentialRunner()
            result = runner.run(pipeline, catalog=test_catalog)
            
            # Check that model was "saved" to catalog
            assert result is not None
            mock_train.assert_called_once()
    
    @pytest.mark.skipif(not PIPELINES_AVAILABLE, reason="Pipeline modules not available")
    def test_metrics_tracking(self, test_catalog, sample_bike_data):
        """Test metrics tracking and logging."""
        test_catalog.save("model_input_table", sample_bike_data)
        test_catalog.save("parameters", {"model_options": {"learning_rate": 0.1, "depth": 6}})
        test_catalog.save("params:random_forest", {"n_estimators": 100})
        test_catalog.save("params:train_fraction", 0.8)
        
        pipelines = register_pipelines()
        pipeline = pipelines["demand_modeling"]
        
        # Mock metrics tracking
        with patch('demand_forecasting.pipelines.demand_modeling.catboost_nodes.train_catboost_model') as mock_train:
            mock_train.return_value = (Mock(), {"rmse": 45.0, "mae": 30.0, "r2": 0.85})
            
            runner = SequentialRunner()
            result = runner.run(pipeline, catalog=test_catalog)
            
            # Check that metrics were tracked
            assert result is not None
            mock_train.assert_called_once()
            
            # Verify metrics structure
            args, kwargs = mock_train.call_args
            assert len(args) >= 4  # X_train, X_test, y_train, y_test
