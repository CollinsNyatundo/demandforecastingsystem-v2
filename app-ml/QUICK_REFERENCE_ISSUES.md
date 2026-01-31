# QUICK REFERENCE: ALL CODE ISSUES

## Total Issues: 29

### CRITICAL (MUST FIX) - 3 Issues

1. ISSUE 14: Model Serialization
   File: demand_modeling/nodes.py
   Risk: Models won't persist correctly

2. ISSUE 15: Pipeline Connections
   File: demand_modeling/pipeline.py
   Risk: Pipeline execution fails

3. ISSUE 16: Column Access Validation
   File: feature_engineering/nodes.py (line 71)
   Risk: KeyError on missing columns

---

### HIGH PRIORITY (SHOULD FIX) - 7 Issues

4. ISSUE 17: Incomplete Catalog
   File: conf/base/catalog.yml
   
5. ISSUE 18: CatBoost Early Stopping
   File: catboost_nodes.py (lines 48, 101)
   
6. ISSUE 19: Optuna Log Scale
   File: catboost_nodes.py (lines 41-45)
   
7. ISSUE 20: Silent Data Loss
   File: feature_engineering/nodes.py
   
8. ISSUE 21: MLflow Context
   File: explainability/nodes.py
   
9. ISSUE 22: DataFrame Performance
   File: feature_engineering/nodes.py
   
10. ISSUE 23: Dataset Size Validation
    File: data_processing/nodes.py

---

### MEDIUM PRIORITY - 8 Issues

11. ISSUE 24: Type Hints (explainability/nodes.py)
12. ISSUE 25: Exception Handling (Multiple files)
13. ISSUE 26: Feature Pipeline (feature_engineering/pipeline.py)
14. ISSUE 27: Parameters YAML (conf/base/parameters.yml)
15. ISSUE 28: NaN Generation (feature_engineering/nodes.py)
16. ISSUE 29: Config Parameters (conf/base/parameters.yml)
17. ISSUE 30: Stub Functions (demand_modeling/nodes.py)
18. ISSUE 31: Logging Coverage (explainability/nodes.py)

---

### LOW PRIORITY - 7 Issues

19. ISSUE 32: DataFrame Index (feature_engineering/nodes.py)
20. ISSUE 33: Hardcoded Values (conf/base/parameters.yml)
21. ISSUE 35: Magic Numbers (catboost_nodes.py)
22. ISSUE 36: Unused Parameters (catboost_nodes.py)
23. ISSUE 37: S3 Hardcoding (Various files)
24. ISSUE 39: Module Docstrings (Various files)
25. ISSUE 40: Function Docstrings (Various files)
26. ISSUE 41: Code Readability (feature_engineering/nodes.py)

---

## FILES REQUIRING FIXES

### Critical Files (Fix First)
- demand_modeling/pipeline.py (Issue 15)
- feature_engineering/nodes.py (Issue 16)
- conf/base/parameters.yml (Issue 27)
- catboost_nodes.py (Issues 18, 19)
- data_processing/nodes.py (Issue 23)

### High Priority Files
- conf/base/catalog.yml (Issue 17)
- feature_engineering/nodes.py (Issues 20, 22, 28, 32)
- explainability/nodes.py (Issue 21)

### Medium Priority Files
- demand_modeling/nodes.py (Issues 24, 30)
- explainability/pipeline.py (Issue 26)

---

## DOCUMENTS GENERATED

1. CODE_ISSUES_IDENTIFIED.md
   - Comprehensive issue list with details
   - Each issue has severity, file, and impact

2. COMPREHENSIVE_SCAN_SUMMARY.md
   - Executive summary of all findings
   - Risk assessment and recommendations
   - Phase-by-phase fix plan

3. QUICK_REFERENCE_ISSUES.md (this file)
   - Quick lookup of all issues
   - Files requiring fixes
   - Priority grouping

---

## NEXT STEPS

1. Review CODE_ISSUES_IDENTIFIED.md for detailed descriptions
2. Decide which phase to proceed with (1, 2, 3, or all)
3. Authorize fixes for selected phase
4. Execute fixes systematically
5. Run validation tests after each phase

Current Status: Issues identified and documented (NOT YET FIXED)
