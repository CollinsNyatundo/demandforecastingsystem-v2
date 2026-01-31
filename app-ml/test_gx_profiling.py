"""
Test Great Expectations profiling implementation.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))


def test_gx_profiling():
    """Test Great Expectations profiling with sample data."""
    print("🧪 Testing Great Expectations Profiling...")

    try:
        from src.demand_forecasting.utils.gx_profiler_simple import profile_dataset_gx

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
        report_path = profile_dataset_gx(
            sample_data,
            "test_dataset",
            docs_dir="/tmp/test_docs",
            enable_data_docs=True,
        )

        print(
            f"✅ Great Expectations profiling test passed! Data Docs at: {report_path}"
        )

        # Test with Data Docs disabled
        disabled_result = profile_dataset_gx(
            sample_data,
            "test_dataset_disabled",
            docs_dir="/tmp/test_docs",
            enable_data_docs=False,
        )

        if disabled_result is None:
            print("✅ Great Expectations profiling disabled correctly!")
        else:
            print(
                "❌ Great Expectations profiling should have returned None when disabled"
            )
            return False

        return True

    except Exception as e:
        print(f"❌ Great Expectations profiling test failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_pipeline_integration():
    """Test pipeline integration with Great Expectations."""
    print("\n🧪 Testing Pipeline Integration...")

    try:
        from src.demand_forecasting.pipelines.data_processing.pipeline import (
            create_pipeline as create_dp_pipeline,
        )

        # Test pipeline creation
        pipeline = create_dp_pipeline()

        print(f"✅ Data processing pipeline created successfully!")
        print(f"✅ Pipeline nodes: {len(pipeline.nodes)}")

        # Check node names
        node_names = [node.name for node in pipeline.nodes]
        print(f"✅ Pipeline nodes: {node_names}")

        # Check if GX profiling node is present
        if "profile_dataset_gx_node" in node_names:
            print("✅ Great Expectations profiling node found in pipeline!")
        else:
            print("❌ Great Expectations profiling node not found in pipeline!")
            return False

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
        with open("conf/base/parameters.yml", "r") as f:
            params = yaml.safe_load(f)

        # Check required parameters
        required_params = ["enable_data_docs", "data_docs_dir", "dataset_name"]
        missing_params = [p for p in required_params if p not in params]

        if missing_params:
            print(f"❌ Missing parameters: {missing_params}")
            return False

        print("✅ All required parameters present!")
        print(f"✅ Enable Data Docs: {params['enable_data_docs']}")
        print(f"✅ Data Docs Dir: {params['data_docs_dir']}")
        print(f"✅ Dataset Name: {params['dataset_name']}")

        return True

    except Exception as e:
        print(f"❌ Parameters configuration test failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run Great Expectations profiling tests."""
    print("🚀 Starting Great Expectations Profiling Tests...\n")

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
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 GREAT EXPECTATIONS TEST SUMMARY")
    print("=" * 50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print(
            "🎉 All Great Expectations tests passed! Profiling is ready for production!"
        )
    else:
        print("⚠️  Some tests failed. Please review the issues above.")


if __name__ == "__main__":
    main()
