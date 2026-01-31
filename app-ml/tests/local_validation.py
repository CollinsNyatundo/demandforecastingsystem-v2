import sys

sys.path.insert(
    0,
    r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml\src",
)

import logging
from typing import Dict, Any
import pandas as pd
import numpy as np

print("=" * 70)
print("COMPREHENSIVE LOCAL VALIDATION TEST SUITE")
print("=" * 70)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

test_results = {"passed": [], "failed": []}

# TEST 1: Catalog validation
print("\n[TEST 1] Catalog YAML Validation")
try:
    import yaml

    catalog_path = r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml\conf\base\catalog.yml"
    with open(catalog_path, "r") as f:
        catalog = yaml.safe_load(f)

    required_datasets = [
        "raw_bike_data",
        "preprocessed_bike_data",
        "X_train",
        "y_train",
        "X_test",
        "y_test",
        "rf_metrics",
        "catboost_model",
        "catboost_metrics",
        "model_comparison",
        "data_docs_report",
    ]

    missing = [ds for ds in required_datasets if ds not in catalog]
    if missing:
        print(f"[FAIL] Missing catalog entries: {missing}")
        test_results["failed"].append("Catalog entries")
    else:
        print("[PASS] All required catalog entries present")
        test_results["passed"].append("Catalog entries")
except Exception as e:
    print(f"[FAIL] Catalog validation error: {e}")
    test_results["failed"].append("Catalog entries")

# TEST 2: Pipeline imports
print("\n[TEST 2] Pipeline Creation & Imports")
try:
    from demand_forecasting.pipelines.explainability import (
        create_pipeline as create_explain,
    )
    from demand_forecasting.pipelines.demand_modeling.pipeline import (
        create_pipeline as create_demand,
    )
    from demand_forecasting.pipelines.feature_engineering.pipeline import (
        create_pipeline as create_features,
    )

    print("[PASS] All pipeline create_pipeline functions importable")
    test_results["passed"].append("Pipeline imports")
except Exception as e:
    print(f"[FAIL] Pipeline import error: {e}")
    test_results["failed"].append("Pipeline imports")

# TEST 3: Node function signatures
print("\n[TEST 3] Node Function Signatures")
try:
    import inspect
    from demand_forecasting.pipelines.explainability.nodes import log_model_artifacts

    sig = inspect.signature(log_model_artifacts)
    params = list(sig.parameters.keys())

    required_params = ["catboost_model", "shap_explanations", "feature_importance"]
    missing_params = [p for p in required_params if p not in params]

    if missing_params:
        print(f"[FAIL] log_model_artifacts missing parameters: {missing_params}")
        test_results["failed"].append("Node signatures")
    else:
        print(f"[PASS] log_model_artifacts has correct signature: {params}")
        test_results["passed"].append("Node signatures")
except Exception as e:
    print(f"[FAIL] Node signature error: {e}")
    test_results["failed"].append("Node signatures")

# TEST 4: Data validation functions
print("\n[TEST 4] Data Validation Functions")
try:
    from demand_forecasting.pipelines.feature_engineering.nodes import validate_features

    test_df = pd.DataFrame(
        {
            "demand": np.random.rand(100),
            "hour": np.random.randint(0, 24, 100),
            "day_of_week": np.random.randint(0, 7, 100),
            "temperature": np.random.rand(100) * 30,
        }
    )

    result = validate_features(test_df)

    if isinstance(result, pd.DataFrame) and len(result) > 0:
        print(
            f"[PASS] validate_features works correctly (output shape: {result.shape})"
        )
        test_results["passed"].append("Data validation")
    else:
        print("[FAIL] validate_features produced unexpected output")
        test_results["failed"].append("Data validation")
except Exception as e:
    print(f"[FAIL] Data validation error: {e}")
    test_results["failed"].append("Data validation")

# TEST 5: Feature extraction
print("\n[TEST 5] Temporal Feature Extraction")
try:
    from demand_forecasting.pipelines.feature_engineering.nodes import (
        extract_temporal_features,
    )

    dates = pd.date_range("2024-01-01", periods=100, freq="H")
    test_df = pd.DataFrame(
        {"demand": np.random.rand(100), "temperature": np.random.rand(100) * 30},
        index=dates,
    )

    result = extract_temporal_features(test_df)

    required_features = ["hour", "day_of_week", "month", "quarter"]
    missing_features = [f for f in required_features if f not in result.columns]

    if not missing_features:
        print(f"[PASS] Temporal features extracted successfully")
        test_results["passed"].append("Feature extraction")
    else:
        print(f"[FAIL] Missing features: {missing_features}")
        test_results["failed"].append("Feature extraction")
except Exception as e:
    print(f"[FAIL] Feature extraction error: {e}")
    test_results["failed"].append("Feature extraction")

# SUMMARY
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Passed: {len(test_results['passed'])} tests")
for test in test_results["passed"]:
    print(f"  [PASS] {test}")

if test_results["failed"]:
    print(f"\nFailed: {len(test_results['failed'])} tests")
    for test in test_results["failed"]:
        print(f"  [FAIL] {test}")
else:
    print("\n[SUCCESS] All local validation tests passed!")

print("=" * 70)
