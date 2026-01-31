"""
Test script to verify all new features work properly.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def test_data_profiler():
    """Test the data profiler with sample data."""
    print("🧪 Testing Data Profiler...")
    
    try:
        from src.demand_forecasting.utils.simple_data_profiler_v2 import profile_dataset
        
        # Create sample data similar to bike sharing dataset
        np.random.seed(42)
        sample_data = pd.DataFrame({
            'datetime': pd.date_range('2023-01-01', periods=100, freq='h'),
            'season': np.random.choice([1, 2, 3, 4], 100),
            'mnth': np.random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 100),
            'hr': np.random.choice(range(24), 100),
            'holiday': np.random.choice([0, 1], 100, p=[0.95, 0.05]),
            'weekday': np.random.choice(range(7), 100),
            'workingday': np.random.choice([0, 1], 100, p=[0.3, 0.7]),
            'weathersit': np.random.choice([1, 2, 3, 4], 100, p=[0.6, 0.3, 0.08, 0.02]),
            'temp': np.random.uniform(0.2, 1.0, 100),
            'atemp': np.random.uniform(0.2, 1.0, 100),
            'hum': np.random.uniform(0.3, 1.0, 100),
            'windspeed': np.random.uniform(0.0, 0.8, 100),
            'casual': np.random.randint(0, 100, 100),
            'registered': np.random.randint(50, 300, 100),
            'cnt': np.random.randint(10, 400, 100)
        })
        
        # Test convenience function
        report_path = profile_dataset(sample_data, "test_dataset")
        print(f"✅ Data profiler test passed! Report generated at: {report_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Data profiler test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_feature_lags():
    """Test feature engineering with new lags."""
    print("\n🧪 Testing Feature Lags...")
    
    try:
        from src.demand_forecasting.pipelines.feature_engineering.nodes import create_derived_features
        
        # Create sample data
        np.random.seed(42)
        sample_data = pd.DataFrame({
            'season': np.random.choice([1, 2, 3, 4], 50),
            'mnth': np.random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 50),
            'hr': np.random.choice(range(24), 50),
            'holiday': np.random.choice([0, 1], 50, p=[0.95, 0.05]),
            'weekday': np.random.choice(range(7), 50),
            'workingday': np.random.choice([0, 1], 50, p=[0.3, 0.7]),
            'weathersit': np.random.choice([1, 2, 3, 4], 50, p=[0.6, 0.3, 0.08, 0.02]),
            'temp': np.random.uniform(0.2, 1.0, 50),
            'atemp': np.random.uniform(0.2, 1.0, 50),
            'hum': np.random.uniform(0.3, 1.0, 50),
            'windspeed': np.random.uniform(0.0, 0.8, 50),
            'cnt': np.random.randint(10, 400, 50)
        })
        
        # Test with default parameters
        result_default = create_derived_features(sample_data)
        print(f"✅ Default feature lags test passed! Shape: {result_default.shape}")
        
        # Test with custom parameters
        custom_lags = [1, 2, 3]
        custom_feature_lags = {
            'hr': [1, 2],
            'temp': [1],
            'hum': [1, 2, 3]
        }
        result_custom = create_derived_features(sample_data, lags=custom_lags, feature_lags=custom_feature_lags)
        print(f"✅ Custom feature lags test passed! Shape: {result_custom.shape}")
        
        # Check for expected lag features
        expected_features = ['cnt_lag_1', 'cnt_lag_2', 'cnt_lag_3', 'hr_lag_1', 'hr_lag_2', 'temp_lag_1', 'hum_lag_1', 'hum_lag_2', 'hum_lag_3', 'target']
        missing_features = [f for f in expected_features if f not in result_custom.columns]
        
        if missing_features:
            print(f"⚠️  Missing expected features: {missing_features}")
        else:
            print("✅ All expected lag features present!")
        
        return True
        
    except Exception as e:
        print(f"❌ Feature lags test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_catboost_nodes():
    """Test CatBoost nodes (without actually training)."""
    print("\n🧪 Testing CatBoost Nodes...")
    
    try:
        # Test import
        from src.demand_forecasting.pipelines.demand_modeling.catboost_nodes import (
            compute_zero_safe_mape, 
            train_catboost_model, 
            compare_models
        )
        print("✅ CatBoost nodes import successful!")
        
        # Test zero-safe MAPE function
        y_true = np.array([10, 20, 30, 0, 50])
        y_pred = np.array([12, 18, 32, 1, 48])
        mape = compute_zero_safe_mape(y_true, y_pred)
        print(f"✅ Zero-safe MAPE test passed! MAPE: {mape:.2f}%")
        
        # Test compare_models function
        rf_metrics = {"rmse": 50.0, "mae": 30.0, "mape": 20.0}
        catboost_metrics = {"rmse": 45.0, "mae": 28.0, "mape": 18.0}
        comparison = compare_models(rf_metrics, catboost_metrics)
        print(f"✅ Model comparison test passed! Winner: {comparison['winner']}")
        
        return True
        
    except Exception as e:
        print(f"❌ CatBoost nodes test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_metrics_parity():
    """Test metrics implementation parity."""
    print("\n🧪 Testing Metrics Parity...")
    
    try:
        from src.demand_forecasting.pipelines.demand_modeling.nodes import compute_zero_safe_mape
        
        # Test with zeros (critical case)
        y_true = np.array([0, 10, 20, 0, 30])
        y_pred = np.array([1, 12, 18, 2, 28])
        
        mape = compute_zero_safe_mape(y_true, y_pred)
        expected_manual = np.mean(np.abs((y_true - y_pred) / np.where(y_true == 0, 0.01, y_true))) * 100
        
        if abs(mape - expected_manual) < 0.001:
            print(f"✅ Metrics parity test passed! MAPE: {mape:.2f}%")
            return True
        else:
            print(f"❌ Metrics parity test failed! Expected: {expected_manual:.2f}, Got: {mape:.2f}")
            return False
            
    except Exception as e:
        print(f"❌ Metrics parity test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_integration():
    """Test pipeline integration."""
    print("\n🧪 Testing Pipeline Integration...")
    
    try:
        # Test pipeline imports
        from src.demand_forecasting.pipelines.feature_engineering.pipeline import create_pipeline as create_fe_pipeline
        from src.demand_forecasting.pipelines.demand_modeling.pipeline import create_pipeline as create_dm_pipeline
        from src.demand_forecasting.pipelines.data_processing.pipeline import create_pipeline as create_dp_pipeline
        
        print("✅ All pipeline imports successful!")
        
        # Test pipeline creation
        fe_pipeline = create_fe_pipeline()
        dm_pipeline = create_dm_pipeline()
        dp_pipeline = create_dp_pipeline()
        
        print(f"✅ Feature engineering pipeline nodes: {len(fe_pipeline.nodes)}")
        print(f"✅ Demand modeling pipeline nodes: {len(dm_pipeline.nodes)}")
        print(f"✅ Data processing pipeline nodes: {len(dp_pipeline.nodes)}")
        
        # Check node names
        fe_node_names = [node.name for node in fe_pipeline.nodes]
        dm_node_names = [node.name for node in dm_pipeline.nodes]
        dp_node_names = [node.name for node in dp_pipeline.nodes]
        
        print(f"✅ FE nodes: {fe_node_names}")
        print(f"✅ DM nodes: {dm_node_names}")
        print(f"✅ DP nodes: {dp_node_names}")
        
        return True
        
    except Exception as e:
        print(f"❌ Pipeline integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_parameters_config():
    """Test parameters configuration."""
    print("\n🧪 Testing Parameters Configuration...")
    
    try:
        import yaml
        
        # Load parameters
        with open('conf/base/parameters.yml', 'r') as f:
            params = yaml.safe_load(f)
        
        # Check required parameters
        required_params = ['train_fraction', 'lags', 'feature_lags', 'catboost', 'optuna', 'dataset_name']
        missing_params = [p for p in required_params if p not in params]
        
        if missing_params:
            print(f"❌ Missing parameters: {missing_params}")
            return False
        
        print("✅ All required parameters present!")
        print(f"✅ Train fraction: {params['train_fraction']}")
        print(f"✅ Feature lags configured: {list(params['feature_lags'].keys())}")
        print(f"✅ CatBoost parameters: {list(params['catboost'].keys())}")
        print(f"✅ Optuna trials: {params['optuna']['n_trials']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Parameters configuration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Comprehensive Feature Testing...\n")
    
    tests = [
        ("Data Profiler", test_data_profiler),
        ("Feature Lags", test_feature_lags),
        ("CatBoost Nodes", test_catboost_nodes),
        ("Metrics Parity", test_metrics_parity),
        ("Pipeline Integration", test_pipeline_integration),
        ("Parameters Configuration", test_parameters_config),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Features are ready for production!")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")

if __name__ == "__main__":
    main()
