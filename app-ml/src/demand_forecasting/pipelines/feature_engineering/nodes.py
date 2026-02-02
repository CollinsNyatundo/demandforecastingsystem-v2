"""Feature Engineering Nodes.

Temporal feature extraction, validation, and feature interaction creation.
"""

import logging

import pandas as pd

_LOGGER = logging.getLogger(__name__)

# Feature engineering constants
MIN_FEATURE_COUNT_THRESHOLD = 50


def validate_etl_data(df: pd.DataFrame, stage_name: str) -> bool:
    """Validate data integrity at each ETL stage.

    Args:
        df: DataFrame to validate
        stage_name: Name of the processing stage

    Returns:
        True if validation passes, False otherwise
    """
    _LOGGER.info(f"Validating data at {stage_name}...")

    try:
        # Check for null values
        null_count = df.isnull().sum().sum()
        if null_count > 0:
            _LOGGER.warning(f"Found {null_count} null values at {stage_name}")

        # Check for duplicates
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            _LOGGER.warning(f"Found {duplicate_count} duplicate rows at {stage_name}")

        _LOGGER.info(f"Validation passed for {stage_name}")
        return True

    except Exception as e:
        _LOGGER.error(f"Validation failed at {stage_name}: {e}")
        return False


def extract_temporal_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract temporal features from datetime index.

    Args:
        df: Input DataFrame with datetime index

    Returns:
        DataFrame with extracted temporal features
    """
    _LOGGER.info("Extracting temporal features...")

    try:
        df = df.copy()

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Extract temporal features
        df["hour"] = df.index.hour
        df["day_of_week"] = df.index.dayofweek
        df["month"] = df.index.month
        df["quarter"] = df.index.quarter
        df["day_of_year"] = df.index.dayofyear

        _LOGGER.info(f"Extracted temporal features. Shape: {df.shape}")
        return df

    except Exception as e:
        _LOGGER.error(f"Failed to extract temporal features: {e}")
        raise


def create_feature_interactions(
    df: pd.DataFrame,
    lags: list[int] | None = None,
    feature_lags: dict[str, list[int]] | None = None,
) -> pd.DataFrame:
    """Create feature interactions and lag features with memory optimization.

    Args:
        df: Input DataFrame with base features
        lags: List of lag values for target variable
        feature_lags: Dictionary mapping feature names to lag values

    Returns:
        DataFrame with interaction and lag features added
    """
    _LOGGER.info("Creating feature interactions and lags...")

    try:
        # Use inplace operations to reduce memory usage
        # Only copy if we need to preserve original
        if len(df.columns) > MIN_FEATURE_COUNT_THRESHOLD:  # Large DataFrame threshold
            df = df.copy(deep=False)  # Shallow copy for memory efficiency
        else:
            df = df.copy()

        # Default lag configurations
        if lags is None:
            lags = [1, 2, 22, 23]
        if feature_lags is None:
            feature_lags = {}

        # Create target lags (if 'demand' or 'cnt' column exists)
        target_col = (
            "demand"
            if "demand" in df.columns
            else "cnt" if "cnt" in df.columns else None
        )

        if target_col:
            # Vectorized lag creation for better performance
            for lag in lags:
                df[f"{target_col}_lag{lag}"] = df[target_col].shift(lag)

        # Create feature lags with memory optimization
        for feature, lag_values in feature_lags.items():
            if feature in df.columns:
                for lag in lag_values:
                    df[f"{feature}_lag{lag}"] = df[feature].shift(lag)

        # Optimize memory usage by downcasting numeric columns
        for col in df.select_dtypes(include=["int64"]).columns:
            df[col] = pd.to_numeric(df[col], downcast="integer")

        for col in df.select_dtypes(include=["float64"]).columns:
            df[col] = pd.to_numeric(df[col], downcast="float")

        # Create some basic interactions
        if "hour" in df.columns and "day_of_week" in df.columns:
            df["hour_day_interaction"] = df["hour"] * df["day_of_week"]

        # Handle missing values from lagging using backward fill (bfill)
        # bfill() fills NaN values with the next available value, then forward fill remaining NaN
        # This is better than dropna() which loses data
        df = df.bfill().ffill()

        _LOGGER.info(f"Created interactions and lags. New shape: {df.shape}")
        return df

    except Exception as e:
        _LOGGER.error(f"Failed to create feature interactions: {e}")
        raise


def validate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Validate engineered features for model training.

    Args:
        df: DataFrame with engineered features

    Returns:
        Validated DataFrame ready for model training
    """
    _LOGGER.info("Validating engineered features...")

    try:
        df = df.copy()

        # Check for required columns
        required_base = ["demand", "hour", "day_of_week"]
        missing = [col for col in required_base if col not in df.columns]

        if missing:
            _LOGGER.warning(f"Missing expected columns: {missing}")

        # Handle any remaining NaN values using forward/backward fill instead of dropping
        len(df)
        df = df.bfill().ffill()
        removed = 0  # We're not removing rows, just filling NaN values

        if removed > 0:
            _LOGGER.warning(f"Removed {removed} rows with NaN values during validation")

        # Check data types
        for col in df.select_dtypes(include=["object"]).columns:
            _LOGGER.warning(f"Column '{col}' has object dtype, may need conversion")

        _LOGGER.info(f"Feature validation complete. Final shape: {df.shape}")
        return df

    except Exception as e:
        _LOGGER.error(f"Feature validation failed: {e}")
        raise
