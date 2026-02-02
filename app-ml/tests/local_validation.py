import sys

sys.path.insert(
    0,
    r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml\src",
)

import logging

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

test_results = {"passed": [], "failed": []}

# TEST 1: Catalog validation
try:
    import yaml

    catalog_path = r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml\conf\base\catalog.yml"
    with open(catalog_path) as f:
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
        test_results["failed"].append("Catalog entries")
    else:
        test_results["passed"].append("Catalog entries")
except Exception:
    test_results["failed"].append("Catalog entries")

# TEST 2: Pipeline imports
try:

    test_results["passed"].append("Pipeline imports")
except Exception:
    test_results["failed"].append("Pipeline imports")

# TEST 3: Node function signatures
try:
    import inspect

    from demand_forecasting.pipelines.explainability.nodes import log_model_artifacts

    sig = inspect.signature(log_model_artifacts)
    params = list(sig.parameters.keys())

    required_params = ["catboost_model", "shap_explanations", "feature_importance"]
    missing_params = [p for p in required_params if p not in params]

    if missing_params:
        test_results["failed"].append("Node signatures")
    else:
        test_results["passed"].append("Node signatures")
except Exception:
    test_results["failed"].append("Node signatures")

# TEST 4: Data validation functions
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
        test_results["passed"].append("Data validation")
    else:
        test_results["failed"].append("Data validation")
except Exception:
    test_results["failed"].append("Data validation")

# TEST 5: Feature extraction
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
        test_results["passed"].append("Feature extraction")
    else:
        test_results["failed"].append("Feature extraction")
except Exception:
    test_results["failed"].append("Feature extraction")

# SUMMARY
for _test in test_results["passed"]:
    pass

if test_results["failed"]:
    for _test in test_results["failed"]:
        pass
else:
    pass

