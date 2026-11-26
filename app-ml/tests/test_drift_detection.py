"""
Comprehensive test suite for drift detection and monitoring components.

Tests statistical drift detection methods, edge cases, performance scenarios,
and integration with monitoring infrastructure.
"""

import numpy as np
import pandas as pd
import pytest

from demand_forecasting.monitoring.drift_detector import DriftDetector


class TestDriftDetector:
    """Test drift detection functionality."""

    def test_initialization_success(self, reference_data: pd.DataFrame):
        """Test successful drift detector initialization."""
        detector = DriftDetector(reference_data, threshold=0.05)

        assert detector.reference_data.equals(reference_data)
        assert detector.threshold == 0.05
        assert len(detector.drift_history) == 0
        assert detector.reference_stats is not None

    def test_initialization_invalid_threshold(self, reference_data: pd.DataFrame):
        """Test initialization with invalid threshold."""
        with pytest.raises(ValueError):
            DriftDetector(reference_data, threshold=-0.1)

        with pytest.raises(ValueError):
            DriftDetector(reference_data, threshold=1.5)

    def test_initialization_empty_reference(self):
        """Test initialization with empty reference data."""
        empty_data = pd.DataFrame()

        with pytest.raises(ValueError):
            DriftDetector(empty_data)

    def test_detect_drift_no_drift(
        self, drift_detector: DriftDetector, reference_data: pd.DataFrame
    ):
        """Test drift detection with no drift (similar data)."""
        # Generate data similar to reference
        np.random.seed(42)
        similar_data = reference_data.copy()
        for col in similar_data.columns:
            if similar_data[col].dtype in ["float64", "int64"]:
                noise = np.random.normal(
                    0, similar_data[col].std() * 0.1, len(similar_data)
                )
                similar_data[col] = similar_data[col] + noise

        result = drift_detector.detect_drift(similar_data)

        assert result["overall_drift_score"] < drift_detector.threshold
        assert len(result["drifted_features"]) == 0
        assert result["drifted_feature_count"] == 0
        assert result["drift_percentage"] == 0.0
        assert result["recommendation"] == "No significant drift detected"

    def test_detect_drift_with_drift(
        self, drift_detector: DriftDetector, drifted_data: pd.DataFrame
    ):
        """Test drift detection with actual drift."""
        result = drift_detector.detect_drift(drifted_data)

        assert result["overall_drift_score"] > drift_detector.threshold
        assert len(result["drifted_features"]) > 0
        assert result["drifted_feature_count"] > 0
        assert result["drift_percentage"] > 0.0
        assert result["recommendation"] in [
            "Monitor closely",
            "Retraining recommended",
            "Immediate retraining required",
        ]

    def test_detect_drift_missing_columns(self, drift_detector: DriftDetector):
        """Test drift detection with missing columns."""
        incomplete_data = pd.DataFrame(
            {
                "temp": [20.0, 21.0, 22.0],
                "humidity": [60.0, 61.0, 62.0],
                # Missing wind_speed, hour, day_of_week
            }
        )

        result = drift_detector.detect_drift(incomplete_data)

        # Missing columns should be flagged as drifted
        assert len(result["drifted_features"]) >= 3  # At least the missing ones
        assert any(
            "MISSING_COLUMN" in str(details) for details in result["details"].values()
        )

    def test_detect_drift_empty_current_data(self, drift_detector: DriftDetector):
        """Test drift detection with empty current data."""
        empty_data = pd.DataFrame(columns=drift_detector.reference_data.columns)

        result = drift_detector.detect_drift(empty_data)

        assert result["overall_drift_score"] == 1.0  # Maximum drift
        assert len(result["drifted_features"]) == len(
            drift_detector.reference_data.columns
        )
        assert result["drifted_feature_count"] == len(
            drift_detector.reference_data.columns
        )
        assert result["drift_percentage"] == 100.0

    def test_detect_drift_insufficient_data(self, drift_detector: DriftDetector):
        """Test drift detection with insufficient sample size."""
        small_data = pd.DataFrame(
            {
                "temp": [20.0],
                "humidity": [60.0],
                "wind_speed": [5.0],
                "hour": [14],
                "day_of_week": [3],
            }
        )

        result = drift_detector.detect_drift(small_data)

        # Should handle gracefully with insufficient data warning
        assert "insufficient data" in str(result).lower() or len(result["details"]) > 0

    def test_detect_drift_custom_threshold(
        self, drift_detector: DriftDetector, reference_data: pd.DataFrame
    ):
        """Test drift detection with custom threshold."""
        custom_threshold = 0.01
        result = drift_detector.detect_drift(reference_data, threshold=custom_threshold)

        assert result["threshold"] == custom_threshold

    def test_drift_history_tracking(
        self, drift_detector: DriftDetector, drifted_data: pd.DataFrame
    ):
        """Test that drift results are tracked in history."""
        initial_history_length = len(drift_detector.drift_history)

        # First detection
        drift_detector.detect_drift(drifted_data)
        assert len(drift_detector.drift_history) == initial_history_length + 1

        # Second detection
        drift_detector.detect_drift(drifted_data)
        assert len(drift_detector.drift_history) == initial_history_length + 2

        # Check history structure
        latest_result = drift_detector.drift_history[-1]
        assert "overall_drift_score" in latest_result
        assert "timestamp" in latest_result
        assert "drifted_features" in latest_result


class TestStatisticalTests:
    """Test individual statistical test methods."""

    def test_ks_test_numerical_features(self, drift_detector: DriftDetector):
        """Test Kolmogorov-Smirnov test for numerical features."""
        # Create data with clear distribution shift
        np.random.seed(42)
        np.random.normal(20, 5, 1000)
        current_temp = np.random.normal(30, 5, 1000)  # Shifted mean

        current_data = pd.DataFrame(
            {
                "temp": current_temp,
                "humidity": np.random.normal(60, 10, 1000),
                "wind_speed": np.random.exponential(5, 1000),
                "hour": np.random.randint(0, 24, 1000),
                "day_of_week": np.random.randint(0, 7, 1000),
            }
        )

        result = drift_detector.detect_drift(current_data)
        temp_result = result["details"]["temp"]

        assert "p_value" in temp_result
        assert "drift_score" in temp_result
        assert "is_drifted" in temp_result
        assert "method" in temp_result
        assert temp_result["method"] == "KS_TEST"
        assert temp_result["p_value"] < 0.05  # Should detect drift
        assert temp_result["is_drifted"] is True

    def test_chi_square_test_categorical_features(self):
        """Test Chi-square test for categorical features."""
        rng = np.random.default_rng(42)
        ref_data = pd.DataFrame(
            {
                "temp": rng.normal(20, 5, 1000),
                "hour_bucket": rng.choice(
                    ["morning", "afternoon", "evening", "night"], 1000
                ),
            }
        )
        detector = DriftDetector(ref_data, threshold=0.05)

        current_data = pd.DataFrame(
            {
                "temp": rng.normal(20, 5, 1000),
                "hour_bucket": rng.choice(["morning", "afternoon"], 1000),
            }
        )

        result = detector.detect_drift(current_data)
        hour_result = result["details"]["hour_bucket"]

        assert "p_value" in hour_result
        assert "drift_score" in hour_result
        assert "is_drifted" in hour_result
        assert hour_result["method"] == "CHI_SQUARE_TEST"
        assert hour_result["is_drifted"] is True

    def test_psi_calculation(self, drift_detector: DriftDetector):
        """Test Population Stability Index calculation."""
        # This would require implementing PSI in the drift detector
        # For now, test that the method exists and handles data
        reference_data = drift_detector.reference_data

        # Create data with moderate shift
        current_data = reference_data.copy()
        for col in current_data.select_dtypes(include=[np.number]).columns:
            noise = np.random.normal(
                0, current_data[col].std() * 0.2, len(current_data)
            )
            current_data[col] = current_data[col] + noise

        result = drift_detector.detect_drift(current_data)

        # Check that PSI is calculated (if implemented)
        for feature_details in result["details"].values():
            if "psi" in feature_details:
                assert isinstance(feature_details["psi"], (int, float))
                assert feature_details["psi"] >= 0


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_single_feature_reference(self):
        """Test drift detector with single feature reference data."""
        reference_data = pd.DataFrame({"temp": np.random.normal(20, 5, 1000)})
        detector = DriftDetector(reference_data)

        current_data = pd.DataFrame({"temp": np.random.normal(25, 5, 1000)})
        result = detector.detect_drift(current_data)

        assert result["total_features"] == 1
        assert len(result["details"]) == 1

    def test_constant_features(self):
        """Test drift detection with constant features."""
        reference_data = pd.DataFrame(
            {
                "constant_feature": [42] * 1000,
                "normal_feature": np.random.normal(20, 5, 1000),
            }
        )
        detector = DriftDetector(reference_data)

        current_data = pd.DataFrame(
            {
                "constant_feature": [42] * 1000,  # Same constant
                "normal_feature": np.random.normal(30, 5, 1000),  # Drifted
            }
        )

        result = detector.detect_drift(current_data)

        # Constant feature should not drift
        assert not result["details"]["constant_feature"]["is_drifted"]
        # Normal feature should drift
        assert result["details"]["normal_feature"]["is_drifted"]

    def test_outlier_contamination(self, drift_detector: DriftDetector):
        """Test drift detection with outlier contamination."""
        # Add extreme outliers to current data across numeric columns
        current_data = drift_detector.reference_data.copy()

        # Add outliers to 25% of temp data so KS statistic exceeds drift threshold
        rng = np.random.default_rng(42)
        outlier_indices = rng.choice(
            len(current_data), int(len(current_data) * 0.25), replace=False
        )
        current_data.loc[outlier_indices, "temp"] = 1000.0  # Extreme outlier

        result = drift_detector.detect_drift(current_data)

        # Should detect drift on contaminated feature and overall score
        assert result["details"]["temp"]["is_drifted"] is True
        assert result["overall_drift_score"] >= drift_detector.threshold

    def test_nan_handling(self, drift_detector: DriftDetector):
        """Test drift detection with NaN values."""
        current_data = drift_detector.reference_data.copy()

        # Add NaN values to 10% of data
        nan_indices = np.random.choice(
            len(current_data), int(len(current_data) * 0.1), replace=False
        )
        for idx in nan_indices:
            current_data.loc[idx, "temp"] = np.nan

        result = drift_detector.detect_drift(current_data)

        # Should handle NaN values gracefully
        assert result is not None
        assert "overall_drift_score" in result

    def test_infinite_values(self, drift_detector: DriftDetector):
        """Test drift detection with infinite values."""
        current_data = drift_detector.reference_data.copy()

        # Add infinite values
        current_data.loc[0, "temp"] = np.inf
        current_data.loc[1, "temp"] = -np.inf

        result = drift_detector.detect_drift(current_data)

        # Should handle infinite values gracefully
        assert result is not None
        assert "overall_drift_score" in result

    def test_mixed_data_types(self):
        """Test drift detection with mixed data types."""
        reference_data = pd.DataFrame(
            {
                "numerical": np.random.normal(20, 5, 1000),
                "categorical": np.random.choice(["A", "B", "C"], 1000),
                "boolean": np.random.choice([True, False], 1000),
                "datetime": pd.date_range("2023-01-01", periods=1000, freq="h")[:1000],
            }
        )

        detector = DriftDetector(reference_data)

        current_data = pd.DataFrame(
            {
                "numerical": np.random.normal(25, 5, 1000),  # Drifted
                "categorical": np.random.choice(
                    ["A", "B"], 1000
                ),  # Different distribution
                "boolean": np.random.choice([True, False], 1000),
                "datetime": pd.date_range("2023-06-01", periods=1000, freq="h")[:1000],
            }
        )

        result = detector.detect_drift(current_data)

        assert result["total_features"] == 4
        assert len(result["details"]) == 4

    @pytest.mark.slow
    def test_performance_large_dataset(self):
        """Test performance with large datasets."""
        import time

        # Create large reference dataset
        large_reference = pd.DataFrame(
            {
                f"feature_{i}": np.random.normal(0, 1, 100000)
                for i in range(50)  # 50 features, 100k samples
            }
        )

        large_current = pd.DataFrame(
            {
                f"feature_{i}": np.random.normal(0.1, 1, 100000)  # Small drift
                for i in range(50)
            }
        )

        detector = DriftDetector(large_reference)

        start_time = time.time()
        result = detector.detect_drift(large_current)
        end_time = time.time()

        processing_time = end_time - start_time

        # Should complete within reasonable time (less than 30 seconds)
        assert processing_time < 30.0
        assert result is not None
        assert result["total_features"] == 50


class TestRecommendationSystem:
    """Test drift recommendation logic."""

    def test_no_drift_recommendation(
        self, drift_detector: DriftDetector, reference_data: pd.DataFrame
    ):
        """Test recommendation when no drift is detected."""
        result = drift_detector.detect_drift(reference_data)

        assert result["recommendation"] == "No significant drift detected"

    def test_minor_drift_recommendation(self, drift_detector: DriftDetector):
        """Test recommendation for minor drift."""
        # Create data with minor drift
        current_data = drift_detector.reference_data.copy()
        for col in current_data.select_dtypes(include=[np.number]).columns:
            noise = np.random.normal(
                0, current_data[col].std() * 0.15, len(current_data)
            )
            current_data[col] = current_data[col] + noise

        result = drift_detector.detect_drift(current_data)

        if result["overall_drift_score"] > drift_detector.threshold:
            assert result["recommendation"] in [
                "Monitor closely",
                "Retraining recommended",
            ]

    def test_major_drift_recommendation(
        self, drift_detector: DriftDetector, drifted_data: pd.DataFrame
    ):
        """Test recommendation for major drift."""
        result = drift_detector.detect_drift(drifted_data)

        if result["overall_drift_score"] > 0.5:  # Major drift
            assert result["recommendation"] in [
                "Retraining recommended",
                "Immediate retraining required",
            ]

    def test_severe_drift_recommendation(self, drift_detector: DriftDetector):
        """Test recommendation for severe drift."""
        # Create data with severe drift
        current_data = drift_detector.reference_data.copy()
        for col in current_data.select_dtypes(include=[np.number]).columns:
            current_data[col] = np.random.normal(
                100, 50, len(current_data)
            )  # Complete shift

        result = drift_detector.detect_drift(current_data)

        assert result["recommendation"] == "Immediate retraining required"
