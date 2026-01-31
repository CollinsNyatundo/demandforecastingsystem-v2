# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml\src")

print("=" * 60)
print("IMPORT VALIDATION TEST")
print("=" * 60)

success_count = 0
fail_count = 0

# Test 1: Explainability module exports
try:
    from demand_forecasting.pipelines.explainability import create_pipeline
    print("[PASS] explainability.create_pipeline()")
    success_count += 1
except Exception as e:
    print(f"[FAIL] explainability.create_pipeline(): {e}")
    fail_count += 1

# Test 2: Explainability nodes functions
try:
    from demand_forecasting.pipelines.explainability.nodes import (
        generate_shap_explanations,
        calculate_feature_importance,
        log_model_artifacts,
        create_explainability_report
    )
    print("[PASS] All explainability nodes functions")
    success_count += 1
except Exception as e:
    print(f"[FAIL] Explainability nodes: {e}")
    fail_count += 1

# Test 3: Demand modeling nodes
try:
    from demand_forecasting.pipelines.demand_modeling.nodes import (
        train_single_model,
        train_final_model,
        compare_models
    )
    print("[PASS] Demand modeling nodes functions")
    success_count += 1
except Exception as e:
    print(f"[FAIL] Demand modeling nodes: {e}")
    fail_count += 1

# Test 4: CatBoost nodes
try:
    from demand_forecasting.pipelines.demand_modeling.catboost_nodes import (
        optimize_catboost_params,
        train_catboost_model
    )
    print("[PASS] CatBoost nodes functions")
    success_count += 1
except Exception as e:
    print(f"[FAIL] CatBoost nodes: {e}")
    fail_count += 1

# Test 5: Feature engineering nodes
try:
    from demand_forecasting.pipelines.feature_engineering.nodes import (
        extract_temporal_features,
        validate_features
    )
    print("[PASS] Feature engineering nodes")
    success_count += 1
except Exception as e:
    print(f"[FAIL] Feature engineering nodes: {e}")
    fail_count += 1

print("=" * 60)
print(f"RESULTS: {success_count} passed, {fail_count} failed")
print("=" * 60)
