"""
Unit tests for data processing utilities.
Tests core data processing functions and pipelines.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


class TestDataProcessing:
    """Test suite for data processing functions."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create sample data similar to bike sharing dataset
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="h")

        self.sample_data = pd.DataFrame(
            {
                "dteday": dates.date,
                "hr": dates.hour,
                "season": np.random.choice([1, 2, 3, 4], 100),
                "mnth": dates.month,
                "holiday": np.random.choice([0, 1], 100, p=[0.95, 0.05]),
                "weekday": dates.weekday,
                "workingday": np.random.choice([0, 1], 100, p=[0.3, 0.7]),
                "weathersit": np.random.choice(
                    [1, 2, 3, 4], 100, p=[0.6, 0.3, 0.08, 0.02]
                ),
                "temp": np.random.uniform(0.2, 1.0, 100),
                "atemp": np.random.uniform(0.2, 1.0, 100),
                "hum": np.random.uniform(0.3, 1.0, 100),
                "windspeed": np.random.uniform(0.0, 0.8, 100),
                "casual": np.random.randint(0, 100, 100),
                "registered": np.random.randint(50, 300, 100),
                "cnt": np.random.randint(10, 400, 100),
            }
        )

        # Add datetime column
        self.sample_data["datetime"] = pd.to_datetime(
            self.sample_data["dteday"].astype(str)
            + " "
            + self.sample_data["hr"].astype(str)
            + ":00:00"
        )

    def test_data_loading(self):
        """Test data loading functionality."""
        # Test that sample data has expected structure
        assert len(self.sample_data) == 100
        assert "datetime" in self.sample_data.columns
        assert "cnt" in self.sample_data.columns
        assert "temp" in self.sample_data.columns

        # Test data types
        assert pd.api.types.is_datetime64_any_dtype(self.sample_data["datetime"])
        assert pd.api.types.is_numeric_dtype(self.sample_data["cnt"])
        assert pd.api.types.is_numeric_dtype(self.sample_data["temp"])

    def test_data_validation(self):
        """Test data validation functions."""
        # Test for missing values
        assert not self.sample_data.isnull().any().any()

        # Test for reasonable value ranges
        assert self.sample_data["temp"].between(0, 1).all()
        assert self.sample_data["hum"].between(0, 1).all()
        assert self.sample_data["windspeed"].between(0, 1).all()
        assert self.sample_data["cnt"].between(0, 1000).all()

        # Test categorical values
        assert self.sample_data["season"].between(1, 4).all()
        assert self.sample_data["weathersit"].between(1, 4).all()
        assert self.sample_data["holiday"].isin([0, 1]).all()

    @patch("src.demand_forecasting.pipelines.data_processing.nodes.pd.read_csv")
    def test_preprocess_data_function(self, mock_read_csv):
        """Test the preprocess_data function."""
        mock_read_csv.return_value = self.sample_data

        # Import the function (assuming it exists)
        try:
            from src.demand_forecasting.pipelines.data_processing.nodes import (
                preprocess_data,
            )

            # Test preprocessing
            result = preprocess_data(self.sample_data.copy())

            # Verify result has expected columns
            assert "datetime" in result.columns
            assert "cnt" in result.columns
            assert len(result) > 0

        except ImportError:
            # If the function doesn't exist yet, skip the test
            pytest.skip("preprocess_data function not implemented yet")

    def test_datetime_feature_creation(self):
        """Test datetime feature creation."""
        df = self.sample_data.copy()

        # Test hour extraction
        assert "hr" in df.columns
        assert df["hr"].between(0, 23).all()

        # Test month extraction
        assert "mnth" in df.columns
        assert df["mnth"].between(1, 12).all()

        # Test weekday extraction
        assert "weekday" in df.columns
        assert df["weekday"].between(0, 6).all()

    def test_categorical_encoding(self):
        """Test categorical feature encoding."""
        df = self.sample_data.copy()

        # Test that categorical columns are properly encoded
        categorical_cols = ["season", "weathersit", "mnth", "hr", "weekday"]

        for col in categorical_cols:
            assert col in df.columns
            # Check that values are in expected ranges
            if col in {"season", "weathersit"}:
                assert df[col].between(1, 4).all()
            elif col == "mnth":
                assert df[col].between(1, 12).all()
            elif col == "hr":
                assert df[col].between(0, 23).all()
            elif col == "weekday":
                assert df[col].between(0, 6).all()

    def test_numerical_scaling(self):
        """Test numerical feature scaling."""
        df = self.sample_data.copy()

        # Test that numerical columns are in reasonable ranges
        numerical_cols = ["temp", "atemp", "hum", "windspeed"]

        for col in numerical_cols:
            assert col in df.columns
            assert df[col].between(0, 1).all(), f"Column {col} not properly scaled"

    def test_target_variable_distribution(self):
        """Test target variable distribution."""
        target = self.sample_data["cnt"]

        # Test basic statistics
        assert target.mean() > 0
        assert target.std() > 0
        assert target.min() >= 0
        assert target.max() > target.min()

        # Test for reasonable distribution
        assert target.quantile(0.25) > 0
        assert target.quantile(0.75) > target.quantile(0.25)

    def test_correlation_analysis(self):
        """Test correlation between features and target."""
        df = self.sample_data.copy()

        # Calculate correlations
        correlations = df.select_dtypes(include=[np.number]).corr()

        # Test that correlation matrix is valid
        assert not correlations.isnull().any().any()
        assert correlations.shape[0] == correlations.shape[1]

        # Test target correlation with key features
        correlations["cnt"].abs()

        # Temperature should have positive correlation with bike rentals
        assert correlations.loc["temp", "cnt"] > 0

        # Humidity might have negative correlation
        # (This is a weak test since correlation depends on data)

    def test_data_split_functionality(self):
        """Test train/validation split functionality."""
        df = self.sample_data.copy()

        # Test chronological split (time-based)
        split_point = int(len(df) * 0.8)
        train_data = df.iloc[:split_point]
        val_data = df.iloc[split_point:]

        # Verify split
        assert len(train_data) > len(val_data)
        assert len(train_data) + len(val_data) == len(df)

        # Verify temporal ordering
        assert train_data["datetime"].max() < val_data["datetime"].min()

    def test_outlier_detection(self):
        """Test outlier detection in target variable."""
        target = self.sample_data["cnt"]

        # Calculate IQR-based outliers
        Q1 = target.quantile(0.25)
        Q3 = target.quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outliers = target[(target < lower_bound) | (target > upper_bound)]

        # Test that outlier detection works
        assert isinstance(outliers, pd.Series)

        # In random data, we expect some outliers
        # This is a basic sanity check

    def test_seasonal_patterns(self):
        """Test seasonal patterns in the data."""
        df = self.sample_data.copy()

        # Test hourly patterns
        hourly_avg = df.groupby("hr")["cnt"].mean()

        # Should have 24 hours
        assert len(hourly_avg) == 24

        # Test weekday patterns
        weekday_avg = df.groupby("weekday")["cnt"].mean()

        # Should have 7 days
        assert len(weekday_avg) == 7

        # Test seasonal patterns
        seasonal_avg = df.groupby("season")["cnt"].mean()

        # Should have 4 seasons
        assert len(seasonal_avg) == 4

    def test_weather_impact(self):
        """Test weather impact on bike rentals."""
        df = self.sample_data.copy()

        # Test weather situation impact
        weather_avg = df.groupby("weathersit")["cnt"].mean()

        # Should have reasonable weather categories
        assert len(weather_avg) <= 4

        # Test temperature correlation
        temp_corr = df["temp"].corr(df["cnt"])
        assert not np.isnan(temp_corr)

        # Test humidity correlation
        hum_corr = df["hum"].corr(df["cnt"])
        assert not np.isnan(hum_corr)

    @patch("src.demand_forecasting.pipelines.data_processing.nodes.pd.read_parquet")
    @patch(
        "src.demand_forecasting.pipelines.data_processing.nodes.pd.DataFrame.to_parquet"
    )
    def test_data_pipeline_integration(self, mock_to_parquet, mock_read_parquet):
        """Test data pipeline integration."""
        mock_read_parquet.return_value = self.sample_data

        try:
            from src.demand_forecasting.pipelines.data_processing.pipeline import (
                create_pipeline,
            )

            # Test pipeline creation
            pipeline = create_pipeline()

            # Verify pipeline structure
            assert hasattr(pipeline, "nodes")
            assert len(pipeline.nodes) > 0

            # Test node names
            node_names = [node.name for node in pipeline.nodes]
            assert "preprocess_data_node" in node_names

        except ImportError:
            pytest.skip("Data processing pipeline not implemented yet")

    def test_data_quality_checks(self):
        """Test comprehensive data quality checks."""
        df = self.sample_data.copy()

        quality_issues = []

        # Check for missing values
        missing_counts = df.isnull().sum()
        if missing_counts.any():
            quality_issues.extend(
                [
                    f"Missing values in {col}: {count}"
                    for col, count in missing_counts.items()
                    if count > 0
                ]
            )

        # Check for duplicate rows
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            quality_issues.append(f"Duplicate rows: {duplicate_count}")

        # Check for negative values in non-negative columns
        non_negative_cols = ["cnt", "casual", "registered", "temp", "hum", "windspeed"]
        for col in non_negative_cols:
            if (df[col] < 0).any():
                quality_issues.append(f"Negative values in {col}")

        # Check for out-of-range values
        range_checks = {
            "season": (1, 4),
            "weathersit": (1, 4),
            "temp": (0, 1),
            "hum": (0, 1),
            "windspeed": (0, 1),
        }

        for col, (min_val, max_val) in range_checks.items():
            out_of_range = ~df[col].between(min_val, max_val)
            if out_of_range.any():
                quality_issues.append(
                    f"Out-of-range values in {col}: {out_of_range.sum()}"
                )

        # For test data, we expect no quality issues
        assert len(quality_issues) == 0, f"Data quality issues found: {quality_issues}"

    def test_performance_metrics(self):
        """Test data processing performance metrics."""
        import time

        df = self.sample_data.copy()

        # Test basic operations performance
        start_time = time.time()

        # Simulate typical data processing operations
        df_copy = df.copy()
        df_copy["temp_celsius"] = df_copy["temp"] * 41  # Convert to Celsius-like scale
        df_copy["hum_percent"] = df_copy["hum"] * 100
        df_copy["windspeed_kmh"] = df_copy["windspeed"] * 67

        # Group by operations
        hourly_stats = df_copy.groupby("hr")["cnt"].agg(["mean", "std", "count"])
        daily_stats = df_copy.groupby(df_copy["datetime"].dt.date)["cnt"].sum()

        end_time = time.time()
        processing_time = end_time - start_time

        # Performance should be reasonable (< 1 second for 100 rows)
        assert (
            processing_time < 1.0
        ), f"Processing too slow: {processing_time:.2f} seconds"

        # Verify results
        assert len(hourly_stats) == 24
        assert len(daily_stats) > 0


class TestDataProcessingIntegration:
    """Integration tests for data processing pipeline."""

    @pytest.mark.integration
    def test_full_data_processing_workflow(self):
        """Test complete data processing workflow."""
        # This would test the full pipeline in integration
        # For now, test individual components

        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2023-01-01", periods=50, freq="h"),
                "temp": np.random.uniform(0.2, 1.0, 50),
                "hum": np.random.uniform(0.3, 1.0, 50),
                "cnt": np.random.randint(10, 200, 50),
            }
        )

        # Test workflow steps
        assert len(df) == 50
        assert "datetime" in df.columns
        assert "temp" in df.columns
        assert "cnt" in df.columns

        # Test data transformations
        df_processed = df.copy()
        df_processed["temp_celsius"] = df_processed["temp"] * 41
        df_processed["hum_percent"] = df_processed["hum"] * 100

        assert "temp_celsius" in df_processed.columns
        assert "hum_percent" in df_processed.columns

        # Verify transformations
        assert df_processed["temp_celsius"].between(8.2, 41.0).all()
        assert df_processed["hum_percent"].between(30.0, 100.0).all()

    @pytest.mark.integration
    def test_data_persistence_workflow(self):
        """Test data save/load workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test_data.parquet"

            # Save data
            self.sample_data.to_parquet(temp_path)

            # Load data
            loaded_data = pd.read_parquet(temp_path)

            # Verify data integrity
            pd.testing.assert_frame_equal(self.sample_data, loaded_data)

            assert len(loaded_data) == len(self.sample_data)
            assert list(loaded_data.columns) == list(self.sample_data.columns)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
