# Critical Audit Verification Issues Found

**Status**: AUDIT WORK INCOMPLETE  
**Date**: 2024  
**Severity**: CRITICAL - System cannot execute notebook strategy correctly

---

## Summary

While the code modifications claimed in the audit were partially applied, the **integration layer (Airflow DAG) was not updated to use them correctly**. The system cannot execute the winning strategy from the notebook due to 4 critical issues:

1. **Feature lags not passed to pipeline** - Parameters exist but aren't used
2. **No train/test split** - All data used for training, no held-out validation
3. **Return type mismatch** - Function returns wrong structure for DAG expectations
4. **Hardcoded credentials persist** - Security fixes claim not reflected in code

---

## Critical Issues Detail

### Issue 1: Feature Lags Not Activated in DAG ⚠️ CRITICAL

**Location**: [airflow_dag_enhanced.py](airflow_dag_enhanced.py#L390)

**Problem**:
```python
# Line 390 - WRONG: No parameters passed
derived_df = create_feature_interactions(df_with_temporal)

# Should be:
derived_df = create_feature_interactions(
    df_with_temporal,
    lags=params['feature_engineering']['target_lags'],  # [1, 2, 22, 23]
    feature_lags=params['feature_engineering']['feature_lags']  # hr, weekday, weathersit, temp, hum with [1,2,3]
)
```

**Why It Matters**:
- Parameters ARE defined in `parameters.yml` (confirmed)
- Function supports parameters (code supports lags argument)
- But DAG never passes them
- Result: Model trains WITHOUT lag features despite them being configured
- Expected impact: 15-25% accuracy loss vs. notebook

**Evidence**:
- ✅ [parameters.yml](conf/base/parameters.yml#L21-L30) has feature_lags defined
- ✅ [create_feature_interactions](src/demand_forecasting/pipelines/feature_engineering/nodes.py#L80-90) supports lags parameter
- ❌ DAG doesn't pass them

**Fix Required**: Pass feature_lags from params to function call

---

### Issue 2: No Train/Test Split in DAG ⚠️ CRITICAL

**Location**: [airflow_dag_enhanced.py](airflow_dag_enhanced.py#L485) and [airflow_dag_enhanced.py](airflow_dag_enhanced.py#L510-550)

**Problem**:
```python
# Line 485 - Parameters logged but NEVER USED
"train_fraction": params.get("train_fraction", 0.8),

# Lines 510-550 - ALL data passed to training
X = df.drop('target', axis=1)
y = df['target']

# Then directly:
optimization_result = optimize_catboost_params(X, y, ...)  # Passes 100% of data
train_result = train_catboost_model(X, y, ...)  # Passes 100% of data again
```

**Why It Matters**:
The notebook does this:
```python
# Split 80/20
x_train, x_test, y_train, y_test = prepare_dataset(df, train_fraction=0.8)

# Optimize on train (but optimize_catboost_params does its own 85/15 split)
# Train on 100% of train
# Evaluate on held-out test
metrics = compute_metrics(y_test, predictions)
```

The DAG does this:
```python
# NO split
X = df  # 100% of data

# Optimize on ALL data
optimize_catboost_params(X, y)  # Uses all data, internally does 80/20

# Train on ALL data  
train_catboost_model(X, y)  # Trains on same data used for optimization!

# NO evaluation on held-out set
```

**Expected Impact**:
- Hyperparameters optimized on 100% of training data (should be 80%)
- No way to validate model on unseen data
- No test metrics computed
- Can't verify if model generalizes

**Fix Required**: 
1. Split data 80/20 using train_fraction parameter BEFORE optimization
2. Pass train data to optimize_catboost_params
3. Pass train AND test data to train_catboost_model
4. Return test metrics from training function

---

### Issue 3: train_catboost_model Return Type Mismatch ⚠️ CRITICAL

**Location**: [catboost_nodes.py](src/demand_forecasting/pipelines/demand_modeling/catboost_nodes.py#L165) and [airflow_dag_enhanced.py](airflow_dag_enhanced.py#L535)

**Problem**:
```python
# catboost_nodes.py line 165 - Returns ONLY model
return model

# airflow_dag_enhanced.py line 535 - Tries to unpack TUPLE
catboost_model, catboost_metrics = train_catboost_model(X, y, optimized_params)
```

**Why It Fails**:
This will cause `ValueError: not enough values to unpack` because:
- train_catboost_model returns: `model` (single value)
- DAG expects: `(model, metrics)` (tuple of 2 values)

**Evidence**:
```python
# Line 535 in DAG
catboost_model, catboost_metrics = train_catboost_model(...)
#                               ↑ This unpacking will FAIL
```

**Fix Required**:
```python
def train_catboost_model(X_train, y_train, X_test, y_test, optimized_params):
    # ... train model ...
    predictions = model.predict(X_test)
    metrics = compute_metrics(y_test, predictions)
    return model, metrics
```

---

### Issue 4: Hardcoded AWS Credentials Still Present ⚠️ CRITICAL SECURITY

**Location**: [airflow_dag_enhanced.py](airflow_dag_enhanced.py#L468-L469)

**Problem**:
```python
# Lines 468-469 - HARDCODED CREDENTIALS
os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
```

**Why It's Critical**:
- These are hardcoded default MinIO credentials
- Contradicts security audit claim that "all credentials removed"
- Exposed in source code and git history
- Will fail in production (wrong credentials)
- Security vulnerability: credentials in plain text

**Fix Required**:
```python
# Must come from environment variables
os.environ["AWS_ACCESS_KEY_ID"] = os.environ.get("MINIO_ACCESS_KEY", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ.get("MINIO_SECRET_KEY", "")
os.environ["AWS_DEFAULT_REGION"] = os.environ.get("AWS_REGION", "us-east-1")

# With validation
if not os.environ.get("MINIO_ACCESS_KEY"):
    raise ValueError("MINIO_ACCESS_KEY environment variable not set")
if not os.environ.get("MINIO_SECRET_KEY"):
    raise ValueError("MINIO_SECRET_KEY environment variable not set")
```

---

## Impact Assessment

### Current State
- ❌ Feature engineering features not used (no lag features)
- ❌ No train/test split (model quality unknown)
- ❌ DAG code will crash at line 535 (unpacking error)
- ❌ Hardcoded credentials expose security vulnerability

### After Fixes
- ✅ Feature engineering uses all 15 lag features (matches notebook)
- ✅ Proper 80/20 train/test split (notebook strategy)
- ✅ Model evaluated on held-out test set (quality validated)
- ✅ Hyperparameters tuned on proper optimization set
- ✅ Credentials from environment variables (secure)
- ✅ DAG code executes without errors
- ✅ System replicates notebook winning strategy

---

## Changes Required

| File | Issue | Type | Severity |
|------|-------|------|----------|
| airflow_dag_enhanced.py | Add train/test split | Code | CRITICAL |
| airflow_dag_enhanced.py | Pass feature_lags params | Code | CRITICAL |
| airflow_dag_enhanced.py | Fix hardcoded credentials | Code | CRITICAL |
| catboost_nodes.py | Return (model, metrics) tuple | Code | CRITICAL |
| catboost_nodes.py | Accept X_test, y_test params | Code | CRITICAL |

---

## Recommendation

**Do not deploy** until these issues are fixed. The system:
1. Cannot execute the winning strategy from notebook
2. Will crash at runtime (tuple unpacking)
3. Has unresolved security issues
4. Cannot validate model quality

**Priority**: Implement all 4 fixes immediately before any testing.
