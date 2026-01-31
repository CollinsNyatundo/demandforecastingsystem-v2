#!/usr/bin/env python3
"""
Test Suite for Production Operations Scripts

Tests for:
- Data drift detection
- Automated retraining scheduler
- PostgreSQL integration
- Alert systems

Run with:
    pytest tests/test_production_ops.py -v
    pytest tests/test_production_ops.py::TestDriftDetector -v
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "production_ops"))

# Import modules to test
try:
    from automated_retraining import RetrainingRecord, RetrainingScheduler
    from detect_data_drift import DriftDetector, DriftRecord
except ImportError as e:
    pytest.skip(f"Production ops modules not available: {e}", allow_module_level=True)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def test_db_url():
    """Test database URL (in-memory SQLite)."""
    return "sqlite:///:memory:"


@pytest.fixture
def reference_data():
    """Generate reference dataset for testing."""
    np.random.seed(42)
    n_samples = 1000

    return pd.DataFrame(
        {
            "sales": np.random.normal(100, 20, n_samples),
            "quantity": np.random.poisson(5, n_samples),
            "discount": np.random.uniform(0, 0.3, n_samples),
            "profit": np.random.normal(50, 10, n_samples),
            "category": np.random.choice(["A", "B", "C"], n_samples),
            "region": np.random.choice(["East", "West", "North", "South"], n_samples),
        }
    )


@pytest.fixture
def production_data_no_drift(reference_data):
    """Generate production data with NO drift (same distribution)."""
    np.random.seed(43)
    n_samples = 500

    return pd.DataFrame(
        {
            "sales": np.random.normal(100, 20, n_samples),
            "quantity": np.random.poisson(5, n_samples),
            "discount": np.random.uniform(0, 0.3, n_samples),
            "profit": np.random.normal(50, 10, n_samples),
            "category": np.random.choice(["A", "B", "C"], n_samples),
            "region": np.random.choice(["East", "West", "North", "South"], n_samples),
        }
    )


@pytest.fixture
def production_data_with_drift(reference_data):
    """Generate production data WITH drift (shifted distribution)."""
    np.random.seed(44)
    n_samples = 500

    # Shifted distributions to create drift
    return pd.DataFrame(
        {
            "sales": np.random.normal(120, 25, n_samples),  # Mean shifted up
            "quantity": np.random.poisson(7, n_samples),  # Mean shifted up
            "discount": np.random.uniform(0.1, 0.5, n_samples),  # Range shifted
            "profit": np.random.normal(45, 15, n_samples),  # Mean down, std up
            "category": np.random.choice(
                ["A", "B", "C", "D"], n_samples
            ),  # New category
            "region": np.random.choice(["East", "West"], n_samples),  # Missing regions
        }
    )


@pytest.fixture
def drift_detector(test_db_url):
    """Create DriftDetector instance with test database."""
    detector = DriftDetector(
        storage_url=test_db_url,
        alpha=0.05,
        psi_threshold=0.2,
        wasserstein_threshold=0.1,
    )
    yield detector
    # Cleanup
    detector.engine.dispose()


@pytest.fixture
def retraining_scheduler(test_db_url):
    """Create RetrainingScheduler instance with test database."""
    scheduler = RetrainingScheduler(
        storage_url=test_db_url,
        airflow_url="http://localhost:8080",
        performance_threshold=55.0,
        data_growth_threshold=0.20,
        drift_threshold=3,
    )
    yield scheduler
    # Cleanup
    scheduler.engine.dispose()


# ============================================================================
# Test DriftDetector
# ============================================================================


class TestDriftDetector:
    """Test suite for DriftDetector class."""

    def test_initialization(self, drift_detector):
        """Test DriftDetector initialization."""
        assert drift_detector.alpha == 0.05
        assert drift_detector.psi_threshold == 0.2
        assert drift_detector.wasserstein_threshold == 0.1
        assert drift_detector.engine is not None
        assert drift_detector.Session is not None

    def test_database_table_creation(self, drift_detector):
        """Test that database tables are created."""
        # Check if drift_records table exists
        inspector = drift_detector.engine
        tables = inspector.table_names()
        assert "drift_records" in tables

    def test_detect_no_drift(
        self, drift_detector, reference_data, production_data_no_drift
    ):
        """Test drift detection when there is NO drift."""
        results = drift_detector.detect_drift(
            reference_data=reference_data,
            production_data=production_data_no_drift,
            feature_cols=["sales", "quantity", "discount", "profit"],
        )

        # Should have results for all features
        assert len(results) == 4

        # Most features should not have drift (p-values should be high)
        drift_count = sum(1 for r in results.values() if r["drift_detected"])
        assert (
            drift_count <= 1
        ), "Expected at most 1 feature with drift (false positive)"

    def test_detect_with_drift(
        self, drift_detector, reference_data, production_data_with_drift
    ):
        """Test drift detection when there IS drift."""
        results = drift_detector.detect_drift(
            reference_data=reference_data,
            production_data=production_data_with_drift,
            feature_cols=["sales", "quantity", "discount", "profit"],
        )

        # Should have results for all features
        assert len(results) == 4

        # Multiple features should have drift
        drift_count = sum(1 for r in results.values() if r["drift_detected"])
        assert drift_count >= 2, "Expected at least 2 features with drift"

        # Check that drift_score is calculated
        for feature, result in results.items():
            assert "drift_score" in result
            assert result["drift_score"] >= 0

    def test_continuous_drift_tests(self, drift_detector):
        """Test continuous feature drift detection methods."""
        # Create two clearly different distributions
        reference = pd.Series(np.random.normal(0, 1, 1000))
        production = pd.Series(np.random.normal(2, 1, 1000))  # Shifted mean

        result = drift_detector._test_continuous_drift(
            reference, production, "test_feature"
        )

        # Should detect drift
        assert result["drift_detected"] is True

        # Check all test results are present
        assert "ks_test" in result["tests"]
        assert "psi" in result["tests"]
        assert "wasserstein" in result["tests"]

        # Check statistics
        assert "reference_mean" in result["statistics"]
        assert "production_mean" in result["statistics"]
        assert abs(result["statistics"]["mean_shift"]) > 1.5  # Significant shift

    def test_categorical_drift_tests(self, drift_detector):
        """Test categorical feature drift detection."""
        # Create two different categorical distributions
        reference = pd.Series(
            np.random.choice(["A", "B", "C"], 1000, p=[0.5, 0.3, 0.2])
        )
        production = pd.Series(
            np.random.choice(["A", "B", "C"], 1000, p=[0.2, 0.3, 0.5])
        )

        result = drift_detector._test_categorical_drift(
            reference, production, "test_category"
        )

        # Should detect drift (different distributions)
        assert result["drift_detected"] is True

        # Check test results
        assert "chi_square" in result["tests"]
        assert "psi" in result["tests"]

        # Check statistics
        assert "n_categories_reference" in result["statistics"]
        assert "n_categories_production" in result["statistics"]

    def test_psi_calculation(self, drift_detector):
        """Test PSI calculation."""
        # Same distribution -> low PSI
        reference = pd.Series(np.random.normal(0, 1, 1000))
        production = pd.Series(np.random.normal(0, 1, 1000))
        psi_same = drift_detector._calculate_psi(reference, production)
        assert psi_same < 0.1, "PSI should be low for same distribution"

        # Different distribution -> high PSI
        reference = pd.Series(np.random.normal(0, 1, 1000))
        production = pd.Series(np.random.normal(2, 1, 1000))
        psi_diff = drift_detector._calculate_psi(reference, production)
        assert psi_diff > 0.2, "PSI should be high for different distribution"

    def test_drift_record_storage(
        self, drift_detector, reference_data, production_data_with_drift
    ):
        """Test that drift records are stored in database."""
        results = drift_detector.detect_drift(
            reference_data=reference_data,
            production_data=production_data_with_drift,
            feature_cols=["sales", "quantity"],
        )

        # Retrieve records from database
        history = drift_detector.get_drift_history(days=1)

        # Should have records for all checked features
        assert len(history) >= 2
        assert "sales" in history["feature"].values
        assert "quantity" in history["feature"].values

    def test_drift_history_filtering(
        self, drift_detector, reference_data, production_data_with_drift
    ):
        """Test drift history filtering options."""
        # Create some drift records
        drift_detector.detect_drift(
            reference_data=reference_data,
            production_data=production_data_with_drift,
            feature_cols=["sales", "quantity", "discount"],
        )

        # Test feature filtering
        history = drift_detector.get_drift_history(feature_name="sales", days=1)
        assert all(history["feature"] == "sales")

        # Test drift_only filtering
        history_drift_only = drift_detector.get_drift_history(days=1, drift_only=True)
        assert all(history_drift_only["drift_detected"] == True)

    def test_handle_missing_features(self, drift_detector, reference_data):
        """Test handling of missing features in production data."""
        production_data = reference_data.copy()
        production_data = production_data.drop(columns=["profit"])

        # Should not crash, just skip missing feature
        results = drift_detector.detect_drift(
            reference_data=reference_data,
            production_data=production_data,
            feature_cols=["sales", "profit"],  # profit is missing
        )

        # Should only have results for sales
        assert "sales" in results
        assert "profit" not in results


# ============================================================================
# Test RetrainingScheduler
# ============================================================================


class TestRetrainingScheduler:
    """Test suite for RetrainingScheduler class."""

    def test_initialization(self, retraining_scheduler):
        """Test RetrainingScheduler initialization."""
        assert retraining_scheduler.performance_threshold == 55.0
        assert retraining_scheduler.data_growth_threshold == 0.20
        assert retraining_scheduler.drift_threshold == 3
        assert retraining_scheduler.engine is not None

    def test_database_table_creation(self, retraining_scheduler):
        """Test that database tables are created."""
        inspector = retraining_scheduler.engine
        tables = inspector.table_names()
        assert "retraining_records" in tables

    def test_time_trigger_no_previous(self, retraining_scheduler):
        """Test time trigger when no previous retraining exists."""
        result = retraining_scheduler._check_time_trigger()

        # Should trigger because no previous retraining
        assert result["should_trigger"] is True
        assert result["reason"] == "time_based"
        assert result["days_since_last"] is None

    def test_time_trigger_recent_retraining(self, retraining_scheduler):
        """Test time trigger when recent retraining exists."""
        # Create a recent retraining record
        session = retraining_scheduler.Session()
        record = RetrainingRecord(
            trigger_timestamp=datetime.now() - timedelta(days=2),
            trigger_reason="test",
            completed_timestamp=datetime.now() - timedelta(days=2),
            retraining_status="completed",
        )
        session.add(record)
        session.commit()
        session.close()

        result = retraining_scheduler._check_time_trigger()

        # Should NOT trigger (only 2 days, threshold is 7)
        assert result["should_trigger"] is False
        assert result["days_since_last"] == 2

    def test_time_trigger_old_retraining(self, retraining_scheduler):
        """Test time trigger when old retraining exists."""
        # Create an old retraining record
        session = retraining_scheduler.Session()
        record = RetrainingRecord(
            trigger_timestamp=datetime.now() - timedelta(days=10),
            trigger_reason="test",
            completed_timestamp=datetime.now() - timedelta(days=10),
            retraining_status="completed",
        )
        session.add(record)
        session.commit()
        session.close()

        result = retraining_scheduler._check_time_trigger()

        # Should trigger (10 days > 7 day threshold)
        assert result["should_trigger"] is True
        assert result["days_since_last"] == 10

    def test_performance_trigger_no_metrics(self, retraining_scheduler):
        """Test performance trigger when no metrics available."""
        result = retraining_scheduler._check_performance_trigger()

        # Should not trigger without metrics
        assert result["should_trigger"] is False
        assert result["current_rmse"] is None

    def test_data_trigger_no_previous(self, retraining_scheduler):
        """Test data trigger when no previous retraining."""
        result = retraining_scheduler._check_data_trigger()

        # Should not trigger without baseline
        assert result["should_trigger"] is False

    @patch("automated_retraining.pd.read_csv")
    def test_data_trigger_with_growth(self, mock_read_csv, retraining_scheduler):
        """Test data trigger when data has grown significantly."""
        # Mock current data size
        mock_read_csv.return_value = pd.DataFrame({"col": range(1200)})

        # Create previous retraining record with smaller data size
        session = retraining_scheduler.Session()
        record = RetrainingRecord(
            trigger_timestamp=datetime.now() - timedelta(days=10),
            trigger_reason="test",
            completed_timestamp=datetime.now() - timedelta(days=10),
            retraining_status="completed",
            metadata={"training_data_size": 1000},
        )
        session.add(record)
        session.commit()
        session.close()

        result = retraining_scheduler._check_data_trigger()

        # Should trigger (20% growth: 1000 -> 1200)
        assert result["should_trigger"] is True
        assert result["current_size"] == 1200
        assert result["previous_size"] == 1000
        assert result["growth_rate"] == 0.2

    def test_drift_trigger_no_drift(self, retraining_scheduler):
        """Test drift trigger when no drift detected."""
        result = retraining_scheduler._check_drift_trigger()

        # Should not trigger without drift records
        assert result["should_trigger"] is False
        assert result["n_features"] == 0

    def test_check_retraining_needed_multiple_triggers(self, retraining_scheduler):
        """Test check_retraining_needed with multiple triggers."""
        # This will trigger time-based (no previous retraining)
        should_retrain, triggers = retraining_scheduler.check_retraining_needed()

        assert should_retrain is True
        assert len(triggers) >= 1  # At least time-based trigger

        # Check trigger structure
        for trigger in triggers:
            assert "should_trigger" in trigger
            assert "reason" in trigger
            assert "details" in trigger

    @patch("automated_retraining.requests.post")
    def test_trigger_retraining_dry_run(self, mock_post, retraining_scheduler):
        """Test retraining trigger in dry run mode."""
        triggers = [
            {
                "should_trigger": True,
                "reason": "time_based",
                "details": "Test trigger",
            }
        ]

        dag_run_id = retraining_scheduler.trigger_retraining(
            triggers=triggers, dry_run=True
        )

        # Should not actually trigger
        assert dag_run_id is None
        mock_post.assert_not_called()

    @patch("automated_retraining.requests.post")
    def test_trigger_retraining_success(self, mock_post, retraining_scheduler):
        """Test successful retraining trigger."""
        # Mock successful Airflow API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dag_run_id": "test_run_123"}
        mock_post.return_value = mock_response

        triggers = [
            {
                "should_trigger": True,
                "reason": "time_based",
                "details": "Test trigger",
            }
        ]

        dag_run_id = retraining_scheduler.trigger_retraining(
            triggers=triggers, dry_run=False
        )

        # Should have triggered successfully
        assert dag_run_id == "test_run_123"
        mock_post.assert_called_once()

        # Check that record was created in database
        session = retraining_scheduler.Session()
        records = session.query(RetrainingRecord).all()
        assert len(records) == 1
        assert records[0].dag_run_id == "test_run_123"
        assert records[0].dag_triggered is True
        session.close()

    def test_retraining_history(self, retraining_scheduler):
        """Test retraining history retrieval."""
        # Create some retraining records
        session = retraining_scheduler.Session()
        for i in range(3):
            record = RetrainingRecord(
                trigger_timestamp=datetime.now() - timedelta(days=i),
                trigger_reason="test",
                retraining_status="completed",
                completed_timestamp=datetime.now() - timedelta(days=i),
            )
            session.add(record)
        session.commit()
        session.close()

        # Retrieve history
        history = retraining_scheduler.get_retraining_history(days=7)

        assert len(history) == 3
        assert "timestamp" in history.columns
        assert "reason" in history.columns
        assert "status" in history.columns


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for production operations."""

    def test_drift_to_retraining_workflow(
        self,
        drift_detector,
        retraining_scheduler,
        reference_data,
        production_data_with_drift,
    ):
        """Test full workflow: drift detection -> retraining trigger."""
        # Step 1: Detect drift
        drift_results = drift_detector.detect_drift(
            reference_data=reference_data,
            production_data=production_data_with_drift,
            feature_cols=["sales", "quantity", "discount", "profit"],
        )

        drift_count = sum(1 for r in drift_results.values() if r["drift_detected"])
        assert drift_count >= 2, "Should detect drift in multiple features"

        # Step 2: Check if retraining needed (drift trigger should fire)
        should_retrain, triggers = retraining_scheduler.check_retraining_needed()

        # Should trigger retraining (at least time-based)
        assert should_retrain is True
        assert len(triggers) >= 1

    def test_database_persistence(
        self, drift_detector, reference_data, production_data_with_drift
    ):
        """Test that records persist in database."""
        # Detect drift
        drift_detector.detect_drift(
            reference_data=reference_data,
            production_data=production_data_with_drift,
            feature_cols=["sales", "quantity"],
        )

        # Close and recreate detector (simulates restart)
        storage_url = drift_detector.storage_url
        drift_detector.engine.dispose()

        new_detector = DriftDetector(storage_url=storage_url)

        # Should still have history
        history = new_detector.get_drift_history(days=1)
        assert len(history) >= 2

        new_detector.engine.dispose()


# ============================================================================
# Performance Tests
# ============================================================================


class TestPerformance:
    """Performance tests for production operations."""

    def test_drift_detection_performance(self, drift_detector, benchmark):
        """Test drift detection performance."""
        np.random.seed(42)
        reference = pd.DataFrame(
            {f"feature_{i}": np.random.normal(0, 1, 10000) for i in range(10)}
        )
        production = pd.DataFrame(
            {f"feature_{i}": np.random.normal(0, 1, 5000) for i in range(10)}
        )

        # Should complete in reasonable time
        import time

        start = time.time()
        results = drift_detector.detect_drift(
            reference_data=reference,
            production_data=production,
            feature_cols=[f"feature_{i}" for i in range(10)],
        )
        duration = time.time() - start

        assert duration < 10.0, f"Drift detection too slow: {duration:.2f}s"
        assert len(results) == 10


# ============================================================================
# Utility Tests
# ============================================================================


class TestUtilities:
    """Test utility functions."""

    def test_psi_edge_cases(self, drift_detector):
        """Test PSI calculation edge cases."""
        # Empty series
        reference = pd.Series([])
        production = pd.Series([])
        psi = drift_detector._calculate_psi(reference, production)
        assert psi == 0.0

        # Single value
        reference = pd.Series([1.0])
        production = pd.Series([1.0])
        psi = drift_detector._calculate_psi(reference, production)
        assert psi >= 0.0

        # All same values
        reference = pd.Series([1.0] * 100)
        production = pd.Series([1.0] * 100)
        psi = drift_detector._calculate_psi(reference, production)
        assert psi < 0.1

    def test_categorical_drift_new_categories(self, drift_detector):
        """Test categorical drift with new categories."""
        reference = pd.Series(["A", "B", "C"] * 100)
        production = pd.Series(["A", "B", "C", "D"] * 100)  # New category D

        result = drift_detector._test_categorical_drift(
            reference, production, "test_category"
        )

        # Should detect drift (new category)
        assert result["drift_detected"] is True
        assert "new_categories" in result["statistics"]
        assert "D" in result["statistics"]["new_categories"]


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
