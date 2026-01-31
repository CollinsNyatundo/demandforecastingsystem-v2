# FIX STRATEGY FOR 13 IDENTIFIED ISSUES
## Demand Forecasting ML System

**Date:** January 24, 2026  
**Objective:** Restore system to executable state while maintaining design integrity

---

## STRATEGIC APPROACH

### Phase 1: Foundation (Fix Critical Blocking Issues)
**Goal:** Get pipeline to execute without crashes  
**Effort:** 4-6 issues fixed

### Phase 2: Logic Correction (Fix Pipeline Flow)
**Goal:** Ensure data flows correctly through pipeline  
**Effort:** 3-4 issues fixed

### Phase 3: Quality (Fix Code Quality & Maintainability)
**Goal:** Remove duplication, improve type hints  
**Effort:** 2-3 issues fixed

---

## PHASE 1: CRITICAL BLOCKING ISSUES

### FIX #1: Add Missing Catalog Entries (ISSUE #3)
**Priority:** HIGHEST - blocks entire pipeline  
**Complexity:** LOW - just YAML additions

**What to do:**
Add 5 missing dataset definitions to `conf/base/catalog.yml`:

```yaml
# Add these entries:

rf_metrics:
  type: kedro_datasets.json.JSONDataset
  filepath: s3://demand-forecasting/metrics/rf_metrics.json
  credentials: dev_s3

catboost_model:
  type: kedro_datasets.pickle.PickleDataset
  filepath: s3://demand-forecasting/06_models/catboost_model.pickle
  credentials: dev_s3

catboost_metrics:
  type: kedro_datasets.json.JSONDataset
  filepath: s3://demand-forecasting/metrics/catboost_metrics.json
  credentials: dev_s3

model_comparison:
  type: kedro_datasets.json.JSONDataset
  filepath: s3://demand-forecasting/metrics/model_comparison.json
  credentials: dev_s3

data_docs_report:
  type: kedro_datasets.text.TextDataset
  filepath: s3://demand-forecasting/reports/data_docs_report.html
  credentials: dev_s3
```

**Why:** Without these, Kedro can't save intermediate outputs. Pipeline will crash with `OutputNotFoundError`.

**Impact:** Unblocks all downstream pipeline nodes.

---

### FIX #2: Export create_pipeline from Explainability (ISSUE #2)
**Priority:** HIGHEST - blocks pipeline initialization  
**Complexity:** TRIVIAL - 1 line change

**What to do:**
Update `src/demand_forecasting/pipelines/explainability/__init__.py`:

```python
# Current (broken):
"""Explainability pipeline module."""

# Fixed:
"""Explainability pipeline module."""

from .pipeline import create_pipeline

__all__ = ["create_pipeline"]

__version__ = "0.1"
```

**Why:** `pipeline_registry.py` imports `create_pipeline` but it's not exported.

**Impact:** Unblocks pipeline registry initialization.

---

### FIX #3: Fix Explainability Pipeline Input Names (ISSUE #4)
**Priority:** HIGHEST - blocks explainability execution  
**Complexity:** LOW - mapping correction

**What to do:**
Update `src/demand_forecasting/pipelines/explainability/pipeline.py`:

```python
# Current (broken):
node(
    func=explain_catboost_model,
    inputs=["trained_model", "features"],
    outputs="shap_explanation",
    name="explain_catboost_model",
)

# Fixed:
node(
    func=explain_catboost_model,
    inputs=["catboost_model", "model_input_table"],
    outputs="shap_explanation",
    name="explain_catboost_model",
)
```

**Why:** Pipeline references datasets that don't exist. These are the actual names from the catalog.

**Impact:** Explainability pipeline can now load correct data.

---

### FIX #4: Implement Missing log_model_artifacts() Function (ISSUE #1)
**Priority:** HIGHEST - undefined function call  
**Complexity:** MEDIUM - need proper implementation

**What to do:**
Add to `src/demand_forecasting/utils/__init__.py` export, then create function in utilities.

**Option A: Simple Version** (recommended)
```python
# Add to src/demand_forecasting/utils/s3_helpers.py or new file:

def log_model_artifacts(**artifacts):
    """
    Log model artifacts to MLflow.
    
    Args:
        **artifacts: Key-value pairs of artifact_name=artifact_object
    """
    try:
        import mlflow
        for name, artifact in artifacts.items():
            if artifact is not None:
                # Log as temporary files or artifacts
                mlflow.log_dict(
                    {name: str(artifact)},
                    f"artifacts/{name}.json"
                )
    except Exception as e:
        logger.warning(f"Could not log artifacts to MLflow: {e}")
        # Fail gracefully if MLflow not available
```

**Option B: Remove It** (if not needed)
Simply delete the call from `explainability/nodes.py:31-35` if not critical for production.

**Why:** Function is called but never defined. Causes `NameError` at runtime.

**Impact:** Explainability node can execute without crashing.

---

### FIX #5: Fix SHAP Explainer Attribute (ISSUE #5)
**Priority:** HIGH - runtime crash in explainability  
**Complexity:** LOW - attribute correction

**What to do:**
Update `src/demand_forecasting/pipelines/explainability/nodes.py:40`:

```python
# Current (broken):
return {
    "shap_explanation": explainer.explanation,  # WRONG!
    "shap_values": shap_values,
    "feature_importance": explainer.feature_importances_
}

# Fixed:
return {
    "shap_explanation": explainer.expected_value,  # Correct attribute
    "shap_values": shap_values,
    "feature_importance": explainer.feature_importances_
}
```

**Why:** SHAP's TreeExplainer doesn't have `.explanation` attribute. Should be `.expected_value` (base value).

**Impact:** Explainability node returns valid data structure.

---

## PHASE 2: PIPELINE LOGIC FIXES

### FIX #6: Connect train_final_model to model_comparison (ISSUE #8)
**Priority:** HIGH - breaks optimization pipeline  
**Complexity:** MEDIUM - dependency restructuring

**What to do:**
Update `src/demand_forecasting/pipelines/demand_modeling/pipeline.py`:

**Current (broken):**
```python
node(
    func=train_final_model,
    inputs=["model_input_table", "params:random_forest", "params:train_fraction"],
    outputs="regressor_model",
    name="train_final_model_node",
    tags=["training"],
),
```

**Fixed:**
```python
node(
    func=train_final_model,
    inputs=["model_input_table", "model_comparison", "params:train_fraction"],
    outputs="regressor_model",
    name="train_final_model_node",
    tags=["training"],
),
```

**Also update function signature:**
```python
# In demand_modeling/nodes.py:137
def train_final_model(
    model_input_table: pd.DataFrame,
    model_comparison: Dict[str, Any],  # Changed!
    train_fraction: float = 0.8,
) -> RandomForestRegressor:
    # Extract best params from comparison
    best_params = model_comparison.get("best_params", {})
    if not best_params:
        best_params = model_comparison.get("random_forest", {})
    
    # Rest of function uses best_params...
```

**Why:** Current setup ignores model comparison results. This reconnects the optimization output to final training.

**Impact:** Final model now uses optimized hyperparameters instead of static config.

---

### FIX #7 & #8: Fix Parameter Type Mismatches (ISSUES #6 & #7)
**Priority:** HIGH - misleading function signatures  
**Complexity:** MEDIUM - signature and call correction

**What to do:**

**For train_single_model()** (demand_modeling/nodes.py:65):
```python
# Current (confusing):
def train_single_model(
    model_input_table: pd.DataFrame,
    parameters: Dict[str, Any],  # Expects full dict
    train_fraction: float = 0.8,
    trial_file: str = None,
) -> Dict[str, float]:

# Fixed (honest signature):
def train_single_model(
    model_input_table: pd.DataFrame,
    random_forest_params: Dict[str, Any],  # Explicit!
    train_fraction: float = 0.8,
    trial_file: str = None,
) -> Dict[str, float]:
```

**For train_final_model()** (demand_modeling/nodes.py:137):
Already covered in FIX #6 above - change from `best_params` parameter to receive `model_comparison` dict.

**Why:** Current signatures are misleading. They claim to receive full parameters but actually expect subsets.

**Impact:** Code is now self-documenting and correct.

---

### FIX #9: Fix Feature Engineering Column Validation (ISSUE #9)
**Priority:** MEDIUM-HIGH - data quality issue  
**Complexity:** MEDIUM - validation logic correction

**What to do:**
Update `src/demand_forecasting/pipelines/feature_engineering/nodes.py:6-30`:

```python
# Current (broken - checks for dropped columns):
def validate_etl_data(df: pd.DataFrame, stage_name: str) -> bool:
    if len(df) == 0:
        logger.warning(f"Empty dataframe at {stage_name} stage")
        return False
    
    # Check for required columns (only those actually used in feature engineering)
    required_cols = ['season', 'mnth', 'hr', 'holiday', 'weekday',
                    'workingday', 'weathersit', 'temp', 'atemp', 'hum',
                    'windspeed', 'cnt']  # Includes 'yr' which is dropped!
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        logger.error(f"Missing required columns at {stage_name}: {missing_cols}")
        return False
    
    return True

# Fixed (accounts for preprocessing):
def validate_etl_data(df: pd.DataFrame, stage_name: str) -> bool:
    if len(df) == 0:
        logger.warning(f"Empty dataframe at {stage_name} stage")
        return False
    
    # Different validation based on stage
    if stage_name == "feature_engineering":
        # After preprocessing, these columns are dropped: yr, casual, registered, datetime
        required_cols = ['season', 'mnth', 'hr', 'holiday', 'weekday',
                        'workingday', 'weathersit', 'temp', 'atemp', 'hum',
                        'windspeed', 'cnt']
    else:
        # For raw data validation
        required_cols = ['season', 'yr', 'mnth', 'hr', 'holiday', 'weekday',
                        'workingday', 'weathersit', 'temp', 'atemp', 'hum',
                        'windspeed', 'casual', 'registered', 'cnt']
    
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        logger.error(f"Missing required columns at {stage_name}: {missing_cols}")
        return False
    
    return True
```

**Why:** After preprocessing drops columns, validation fails on removed columns.

**Impact:** Feature engineering properly validates data.

---

### FIX #10: Handle Small Dataset Case Properly (ISSUE #12)
**Priority:** MEDIUM-HIGH - silent failure prevention  
**Complexity:** MEDIUM - conditional logic

**What to do:**
Update `src/demand_forecasting/pipelines/feature_engineering/nodes.py:68-72`:

```python
# Current (returns data without target):
if len(df) <= overall_max_lag:
    logger.warning(f"Dataset too small for lag features. Need at least {overall_max_lag + 1} rows, got {len(df)}")
    return df  # Returns original data without target column!

# Fixed (creates target anyway):
if len(df) <= overall_max_lag:
    logger.warning(f"Dataset too small for lag features. Need at least {overall_max_lag + 1} rows, got {len(df)}")
    logger.warning("Proceeding without lag features, only creating target column...")
    # Still create target for downstream compatibility
    df = df.copy()
    df['target'] = df['cnt'].shift(-1).ffill()
    df = df.dropna()
    return df
```

**Why:** If dataset is too small, returns data without 'target' column, causing `KeyError` downstream.

**Impact:** Graceful degradation - works even with small datasets.

---

## PHASE 3: CODE QUALITY FIXES

### FIX #11: Consolidate Duplicate CatBoost Functions (ISSUE #11)
**Priority:** MEDIUM - maintenance burden  
**Complexity:** HIGH - requires careful refactoring

**What to do:**

Keep `optimize_catboost_hyperparameters()` (lines 218-326)  
Remove/Deprecate `train_catboost_model()` (lines 108-215)

Update `demand_modeling/pipeline.py` to use the consolidated function:

```python
# In pipeline.py:
from .catboost_nodes import optimize_catboost_hyperparameters as train_catboost_model

node(
    func=train_catboost_model,  # Now points to optimize_catboost_hyperparameters
    inputs=["model_input_table", "parameters", "params:train_fraction"],
    outputs=["catboost_model", "catboost_metrics"],
    name="train_catboost_model_node",
    tags=["training"],
),
```

**Why:** Two nearly-identical functions cause maintenance confusion and inconsistency.

**Impact:** Single source of truth for CatBoost training.

---

### FIX #12: Add Proper Type Hints (ISSUE #13)
**Priority:** LOW - quality improvement  
**Complexity:** LOW - just imports and annotations

**What to do:**
Update `src/demand_forecasting/pipelines/feature_engineering/nodes.py`:

```python
# Add imports at top:
from typing import List, Dict, Optional

# Update function signature:
def create_derived_features(
    df: pd.DataFrame, 
    lags: Optional[List[int]] = None,           # Proper typing!
    feature_lags: Optional[Dict[str, List[int]]] = None
) -> pd.DataFrame:
```

**Why:** Bare `list` and `dict` types don't provide full type information.

**Impact:** Better IDE support, mypy validation, developer clarity.

---

## IMPLEMENTATION ORDER (OPTIMAL SEQUENCE)

```
1. FIX #1 - Add catalog entries (unblocks everything)
2. FIX #2 - Export create_pipeline (unblocks initialization)
3. FIX #3 - Fix input names (unblocks explainability)
4. FIX #4 - Implement log_model_artifacts (unblocks explainability)
5. FIX #5 - Fix SHAP attribute (unblocks explainability)
6. FIX #6 - Connect train_final_model (fixes logic)
7. FIX #7 - Fix parameter types (fixes confusing signatures)
8. FIX #9 - Fix validation logic (improves robustness)
9. FIX #10 - Handle small datasets (graceful degradation)
10. FIX #11 - Consolidate functions (code quality)
11. FIX #12 - Add type hints (code quality)
```

---

## ESTIMATED EFFORT

| Phase | Issues | Complexity | Time | Notes |
|-------|--------|-----------|------|-------|
| Phase 1 (Critical) | #1,2,3,4,5 | LOW-MEDIUM | 30-45 min | Mostly configuration + simple function calls |
| Phase 2 (Logic) | #6,7,8,9,10 | MEDIUM-HIGH | 60-90 min | Requires careful testing |
| Phase 3 (Quality) | #11,12 | LOW-MEDIUM | 20-30 min | Refactoring + type hints |
| **TOTAL** | **13** | **MEDIUM** | **2-2.5 hrs** | Full system restoration |

---

## TESTING AFTER EACH FIX

After each phase:
1. `kedro run` - full pipeline execution
2. `pytest tests/ -v` - unit tests
3. `curl http://localhost:8000/health` - API health check

---

## SUCCESS CRITERIA

After all fixes:
✅ Kedro pipeline executes without errors  
✅ All datasets save to catalog  
✅ Model training completes with metrics  
✅ Explainability generates SHAP values  
✅ API serves predictions successfully  
✅ Prometheus metrics collected  
✅ All tests pass  

---

## BEST PRACTICES FOR IMPLEMENTATION

1. **Fix in order** - Don't skip around (Phase 1 unblocks Phase 2)
2. **Test after each fix** - Don't batch test at the end
3. **Review impact** - Check what depends on each fix
4. **Document changes** - Update comments explaining fixes
5. **Version control** - Commit after each phase
6. **Validate data** - Ensure data flows correctly through pipeline

---

**RECOMMENDATION:** Start with Phase 1 immediately. These 5 fixes (30-45 min) will get the system to a runnable state. Then proceed to Phase 2 for correctness, then Phase 3 for quality.
