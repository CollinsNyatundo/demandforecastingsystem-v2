"""Test Great Expectations profiling implementation."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))


def test_gx_profiling() -> bool | None:
    """Test Great Expectations profiling with sample data."""
    try:
        from demand_forecasting.utils.gx_profiler_simple import profile_dataset_gx

        # Create sample data similar to bike sharing dataset
        np.random.seed(42)
        sample_data = pd.DataFrame(
            {
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

        # Test with Data Docs enabled
        profile_dataset_gx(
            sample_data,
            "test_dataset",
            docs_dir="/tmp/test_docs",
            enable_data_docs=True,
        )

        # Test with Data Docs disabled
        disabled_result = profile_dataset_gx(
            sample_data,
            "test_dataset_disabled",
            docs_dir="/tmp/test_docs",
            enable_data_docs=False,
        )

        if disabled_result is None:
            pass
        else:
            return False

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def test_pipeline_integration() -> bool | None:
    """Test pipeline integration with Great Expectations."""
    try:
        from demand_forecasting.pipelines.data_processing.pipeline import (
            create_pipeline as create_dp_pipeline,
        )

        # Test pipeline creation
        pipeline = create_dp_pipeline()

        # Check node names
        node_names = [node.name for node in pipeline.nodes]

        # Check if GX profiling node is present
        if "profile_dataset_gx_node" in node_names:
            pass
        else:
            return False

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
        required_params = ["enable_data_docs", "data_docs_dir", "dataset_name"]
        missing_params = [p for p in required_params if p not in params]

        return not missing_params

    except Exception:
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run Great Expectations profiling tests."""
    tests = [
        ("Great Expectations Profiling", test_gx_profiling),
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
