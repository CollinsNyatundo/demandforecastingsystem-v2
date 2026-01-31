# ML System Test Suite

This directory contains comprehensive unit and integration tests for the demand forecasting ML system.

## 🗂️ Test Structure

```
tests/
├── test_runner.py          # Main test runner script
├── test_minio_upload.py    # MinIO upload functionality tests
├── test_s3_helpers.py      # S3 helper utilities tests
├── test_data_processing.py # Data processing pipeline tests
├── test_automation.py      # Retraining automation tests
├── test_core_utilities.py  # Core utility function tests
├── test_drift_detection.py # Data drift detection tests
├── test_explainability.py  # SHAP explainability tests
├── test_integration.py     # End-to-end integration tests
├── test_model_serving.py   # Model serving API tests
├── test_optimization.py    # Optuna optimization tests
├── test_production_ops.py  # Production operations tests
├── pipelines/              # Pipeline-specific tests
│   └── test_data_processing.py
├── conftest.py             # Pytest configuration and fixtures
└── README.md              # This file
```

## 🚀 Quick Start

### Run All Tests
```bash
# From project root
cd app-ml

# Run comprehensive test suite
python tests/test_runner.py

# Or with pytest directly
pytest tests/ -v --cov=src/demand_forecasting --cov-report=html
```

### Run Specific Test Suites
```bash
# Unit tests only
python tests/test_runner.py --suite unit

# Integration tests only
python tests/test_runner.py --suite integration

# ML pipeline tests only
python tests/test_runner.py --suite ml

# System tests only
python tests/test_runner.py --suite system
```

### Run Individual Test Files
```bash
# Run specific test file
pytest tests/test_minio_upload.py -v

# Run with coverage
pytest tests/test_s3_helpers.py --cov=src/demand_forecasting --cov-report=term-missing
```

## 📊 Test Categories

### Unit Tests (`test_*_unit.py`)
- Test individual functions and methods
- Mock external dependencies
- Fast execution (< 1 second per test)
- High coverage target (>90%)

### Integration Tests (`test_*_integration.py`)
- Test component interactions
- May use real dependencies
- Medium execution time (1-10 seconds)
- Test realistic scenarios

### System Tests (`test_*_system.py`)
- Test end-to-end workflows
- May require running services
- Longer execution time (10+ seconds)
- Marked with `@pytest.mark.integration`

## 🛠️ Test Configuration

### Pytest Configuration (`pytest.ini`)
```ini
[tool:pytest.ini_options]
addopts = """
--cov-report term-missing \
--cov src/demand_forecasting -ra
"""
```

### Coverage Configuration
- Target coverage: >90% for core modules
- Excluded files: `__init__.py`, test files
- HTML reports: `htmlcov/index.html`

### Test Fixtures (`conftest.py`)
- Common test data fixtures
- Mock objects and patches
- Database connections (for integration tests)
- Temporary directories and files

## 🎯 Test Naming Conventions

### Test Functions
```python
def test_function_name():
    """Test that function_name works correctly."""
    # Arrange
    # Act
    # Assert

def test_function_name_with_edge_case():
    """Test function_name with edge case scenario."""
    # Test edge cases and error conditions
```

### Test Classes
```python
class TestComponentName:
    """Test suite for ComponentName functionality."""

    def test_method_name(self):
        """Test ComponentName.method_name()."""
        pass

    def test_method_name_edge_case(self):
        """Test ComponentName.method_name() edge case."""
        pass
```

## 🔧 Running Tests in Different Environments

### Local Development
```bash
# Activate conda environment
conda activate demand-forecasting

# Run tests
pytest tests/ -v
```

### Docker Environment
```bash
# Run tests in Docker container
docker-compose exec airflow-worker pytest /opt/airflow/tests -v

# Run with coverage
docker-compose exec airflow-worker pytest /opt/airflow/tests --cov=/opt/airflow/src
```

### CI/CD Pipeline
```bash
# Run tests with JUnit output for CI
pytest tests/ --junitxml=test-results.xml --cov-report=xml

# Run only fast tests in CI
pytest tests/ -m "not slow" --maxfail=5
```

## 📈 Test Reports

### HTML Coverage Report
```bash
pytest tests/ --cov=src/demand_forecasting --cov-report=html
# Open htmlcov/index.html in browser
```

### JSON Coverage Report
```bash
pytest tests/ --cov=src/demand_forecasting --cov-report=json
# Parse coverage.json for CI integration
```

### Test Results XML
```bash
pytest tests/ --junitxml=test-results.xml
# Import into CI/CD tools like Jenkins, GitLab CI
```

## 🏷️ Test Markers

### Built-in Markers
```python
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.xfail(reason="Known issue")
def test_known_bug():
    pass
```

### Custom Markers
```python
@pytest.mark.integration
def test_full_system_integration():
    """Requires running services."""
    pass

@pytest.mark.slow
def test_performance_heavy_operation():
    """Takes >30 seconds to run."""
    pass

@pytest.mark.gpu
def test_gpu_accelerated_feature():
    """Requires GPU hardware."""
    pass
```

## 🐛 Debugging Tests

### Verbose Output
```bash
# Show all output
pytest tests/test_specific.py -v -s

# Show captured output on failure
pytest tests/ -v --tb=long
```

### Debug Specific Test
```bash
# Run single test with debugger
pytest tests/test_specific.py::TestClass::test_method -v -s --pdb
```

### Profile Test Performance
```bash
# Show slowest tests
pytest tests/ --durations=10

# Profile memory usage
pytest tests/ --memray
```

## 📝 Writing New Tests

### 1. Create Test File
```bash
# Create new test file
touch tests/test_new_feature.py
```

### 2. Add Test Structure
```python
"""
Tests for new_feature module.
"""

import pytest
from src.demand_forecasting.new_feature import NewFeatureClass


class TestNewFeature:
    """Test suite for NewFeatureClass."""

    def setup_method(self):
        """Set up test fixtures."""
        self.feature = NewFeatureClass()

    def test_basic_functionality(self):
        """Test basic feature operation."""
        result = self.feature.do_something("input")
        assert result == "expected_output"

    def test_error_handling(self):
        """Test error conditions."""
        with pytest.raises(ValueError):
            self.feature.do_something(None)

    def test_edge_cases(self):
        """Test edge cases."""
        # Test empty input
        result = self.feature.do_something("")
        assert result == ""

        # Test large input
        large_input = "x" * 10000
        result = self.feature.do_something(large_input)
        assert len(result) > 0
```

### 3. Add to Test Runner
Update `test_runner.py` to include the new test file in the appropriate suite.

### 4. Run and Verify
```bash
# Run new test
pytest tests/test_new_feature.py -v

# Check coverage
pytest tests/test_new_feature.py --cov=src/demand_forecasting.new_feature --cov-report=term-missing
```

## 🎯 Test Quality Guidelines

### ✅ Good Test Practices
- **Descriptive names**: `test_user_login_with_valid_credentials()`
- **Single responsibility**: One assertion per test
- **Independent**: Tests don't depend on each other
- **Fast**: Unit tests < 0.1s, integration < 5s
- **Isolated**: Mock external dependencies
- **Repeatable**: Same result every run

### ❌ Anti-patterns to Avoid
- **Magic numbers**: Use named constants
- **Complex setup**: Extract to fixtures
- **Sleep() calls**: Use proper synchronization
- **Testing implementation**: Test behavior, not code
- **Duplicate code**: Extract common test utilities

### 📏 Test Metrics Targets
- **Coverage**: >90% for core modules
- **Execution time**: < 5 minutes total
- **Failure rate**: < 1% (flaky tests)
- **Maintainability**: < 10 lines of test code per line of production code

## 🔗 Related Documentation

- [Main README](../README.md) - Project overview
- [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) - Deployment guide
- [docs/ENVIRONMENT_SETUP.md](../docs/ENVIRONMENT_SETUP.md) - Environment setup
- [analysis_reports/IMPLEMENTATION_SUMMARY.md](../analysis_reports/IMPLEMENTATION_SUMMARY.md) - Implementation details

## 📞 Support

For questions about tests:
1. Check existing test examples
2. Review pytest documentation
3. Ask in development team chat
4. Create issue with test case details

---

**Test Suite Version:** 1.0.0
**Last Updated:** January 2025
**Coverage Target:** >90%
**Total Tests:** 40+ (planned)
