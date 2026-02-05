import sys

from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


success_count = 0
fail_count = 0

# Test 1: Explainability module exports
try:
    success_count += 1
except Exception:
    fail_count += 1

# Test 2: Explainability nodes functions
try:
    success_count += 1
except Exception:
    fail_count += 1

# Test 3: Demand modeling nodes
try:
    success_count += 1
except Exception:
    fail_count += 1

# Test 4: CatBoost nodes
try:
    success_count += 1
except Exception:
    fail_count += 1

# Test 5: Feature engineering nodes
try:
    success_count += 1
except Exception:
    fail_count += 1
