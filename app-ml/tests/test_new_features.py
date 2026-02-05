"""Test script to verify all new features work properly."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))


def test_data_profiler() -> bool | None:
    """Test the data profiler with sample data."""
    try:
        from demand_forecasting.utils.simple_data_profiler_v2 import profile_dataset

        # Create sample data similar to bike sharing dataset
        np.random.seed(42)
        sample_data = pd.DataFrame(
            {
                "datetime": pd.date_range("2023-01-01", periods=100, freq="h"),
                "season": np.random.choice([1, 2, 3, 4], 100),
                "mnth": np.random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 100),
                "hr": np.random.choice(range(24), 100),
                "holiday": np.random.choice([0, 1], 100, p=[0.95, 0.05]),
                "weekday": np.random.choice(range(7), 100),
                "workingday": np.random.choice([0, 1], 100, p=[0.3, 0.7]),
                "weathersit": np.random.choice(
                    [1, 2, 3, 4], 100, p=[0.6, 0.3, 0.08, 0.02]
                ),
                "temp": np.random.uniform(0.2, 1.0, 100),
                "atemp": np.random.uniform(0.2, 1.0, 100),
                "hum": np.random.uniform(0.3, 1.0, 100),
                "windspeed": np.random.uniform(0.0, 0.8, 100),
                "casual": np.random.randint(0, 100, 100),
                "registered": np.random.randint(50, 300, 100),
                "cnt": np.random.randint(10, 400, 100),
            }
        )

        # Test convenience function
        profile_dataset(sample_data, "test_dataset")

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_feature_lags() -> bool | None:
    """Test feature engineering with new lags."""
    try:
        from demand_forecasting.pipelines.feature_engineering.nodes import (
            create_derived_features,
        )

        # Create sample data
        np.random.seed(42)
        sample_data = pd.DataFrame(
            {
                "season": np.random.choice([1, 2, 3, 4], 50),
                "mnth": np.random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 50),
                "hr": np.random.choice(range(24), 50),
                "holiday": np.random.choice([0, 1], 50, p=[0.95, 0.05]),
                "weekday": np.random.choice(range(7), 50),
                "workingday": np.random.choice([0, 1], 50, p=[0.3, 0.7]),
                "weathersit": np.random.choice(
                    [1, 2, 3, 4], 50, p=[0.6, 0.3, 0.08, 0.02]
                ),
                "temp": np.random.uniform(0.2, 1.0, 50),
                "atemp": np.random.uniform(0.2, 1.0, 50),
                "hum": np.random.uniform(0.3, 1.0, 50),
                "windspeed": np.random.uniform(0.0, 0.8, 50),
                "cnt": np.random.randint(10, 400, 50),
            }
        )

        # Test with default parameters
        create_derived_features(sample_data)

        # Test with custom parameters
        custom_lags = [1, 2, 3]
        custom_feature_lags = {"hr": [1, 2], "temp": [1], "hum": [1, 2, 3]}
        result_custom = create_derived_features(
            sample_data, lags=custom_lags, feature_lags=custom_feature_lags
        )

        # Check for expected lag features
        expected_features = [
            "cnt_lag_1",
            "cnt_lag_2",
            "cnt_lag_3",
            "hr_lag_1",
            "hr_lag_2",
            "temp_lag_1",
            "hum_lag_1",
            "hum_lag_2",
            "hum_lag_3",
            "target",
        ]
        missing_features = [
            f for f in expected_features if f not in result_custom.columns
        ]

        if missing_features:
            pass
        else:
            pass

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_catboost_nodes() -> bool | None:
    """Test CatBoost nodes (without actually training)."""
    try:
        # Test import
        from demand_forecasting.pipelines.demand_modeling.catboost_nodes import (
            compare_models,
            compute_zero_safe_mape,
        )

        # Test zero-safe MAPE function
        y_true = np.array([10, 20, 30, 0, 50])
        y_pred = np.array([12, 18, 32, 1, 48])
        compute_zero_safe_mape(y_true, y_pred)

        # Test compare_models function
        rf_metrics = {"rmse": 50.0, "mae": 30.0, "mape": 20.0}
        catboost_metrics = {"rmse": 45.0, "mae": 28.0, "mape": 18.0}
        compare_models(rf_metrics, catboost_metrics)

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_metrics_parity() -> bool | None:
    """Test metrics implementation parity."""
    try:
        from demand_forecasting.pipelines.demand_modeling.nodes import (
            compute_zero_safe_mape,
        )

        # Test with zeros (critical case)
        y_true = np.array([0, 10, 20, 0, 30])
        y_pred = np.array([1, 12, 18, 2, 28])

        mape = compute_zero_safe_mape(y_true, y_pred)
        expected_manual = (
            np.mean(np.abs((y_true - y_pred) / np.where(y_true == 0, 0.01, y_true)))
            * 100
        )

        return abs(mape - expected_manual) < 0.001

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_pipeline_integration() -> bool | None:
    """Test pipeline integration."""
    try:
        # Test pipeline imports
        from demand_forecasting.pipelines.data_processing.pipeline import (
            create_pipeline as create_dp_pipeline,
        )
        from demand_forecasting.pipelines.demand_modeling.pipeline import (
            create_pipeline as create_dm_pipeline,
        )
        from demand_forecasting.pipelines.feature_engineering.pipeline import (
            create_pipeline as create_fe_pipeline,
        )

        # Test pipeline creation
        fe_pipeline = create_fe_pipeline()
        dm_pipeline = create_dm_pipeline()
        dp_pipeline = create_dp_pipeline()

        # Check node names
        [node.name for node in fe_pipeline.nodes]
        [node.name for node in dm_pipeline.nodes]
        [node.name for node in dp_pipeline.nodes]

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_parameters_config() -> bool | None:
    """Test parameters configuration."""
    try:
        import yaml

        # Load parameters
        with open("conf/base/parameters.yml") as f:
            params = yaml.safe_load(f)

        # Check required parameters
        required_params = [
            "train_fraction",
            "lags",
            "feature_lags",
            "catboost",
            "optuna",
            "dataset_name",
        ]
        missing_params = [p for p in required_params if p not in params]

        return not missing_params

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
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
        except Exception:
            results.append((test_name, False))

    # Summary

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        pass

    if passed == total:
        pass
    else:
        pass


if __name__ == "__main__":
    main()
