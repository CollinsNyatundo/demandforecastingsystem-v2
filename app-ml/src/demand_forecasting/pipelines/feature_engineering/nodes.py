"""Feature Engineering Nodes.

Temporal feature extraction, validation, and feature interaction creation.
"""

import logging
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

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


def create_feature_interactions(  # noqa: C901, PLR0912
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
        DataFrame with interaction and lag features added, including 'target' column
    """
    _LOGGER.info("Creating feature interactions and lags...")

    try:
        # Use inplace operations to reduce memory usage
        # Only copy if we need to preserve original
        if len(df.columns) > MIN_FEATURE_COUNT_THRESHOLD:  # Large DataFrame threshold
            df = df.copy(deep=False)  # Shallow copy for memory efficiency
        else:
            df = df.copy()

        # Default lag configurations matching notebook experimentation
        # Notebook: "We see that the autocorrelations are high for the first and last 3 values
        # that indicates a strong daily seasonality."
        if lags is None:
            lags = [1, 2, 22, 23]  # Demand lags based on autocorrelation analysis
        
        # Default feature lags matching notebook:
        # lag_feats = ['hr', 'weekday', 'weathersit', 'temp', 'hum']
        # for feat in lag_feats: for i in range(1, n+1): df[f'{feat}_lag_{i}'] = ...
        if feature_lags is None:
            feature_lags = {
                "hour": [1, 2, 3],
                "day_of_week": [1, 2, 3],
                "weather_condition": [1, 2, 3],
                "temp": [1, 2, 3],
                "humidity": [1, 2, 3],
            }

        # Standardize column names from raw data format
        # This ensures consistency across the pipeline
        column_mapping = {
            "cnt": "demand",       # Total bike count -> demand (target source)
            "hr": "hour",          # Hour of day
            "hum": "humidity",     # Humidity
            "windspeed": "wind_speed",  # Wind speed
            "weekday": "day_of_week",   # Day of week
            "mnth": "month",       # Month
            "yr": "year",          # Year
            "atemp": "feels_like_temp",  # Feels like temperature
            "weathersit": "weather_condition",  # Weather situation
        }

        # Apply column renaming (only for columns that exist AND target name doesn't exist)
        # This prevents duplicate columns when temporal features already exist
        existing_renames = {
            k: v for k, v in column_mapping.items() 
            if k in df.columns and v not in df.columns
        }
        
        # For columns where target already exists, drop the source column instead
        cols_to_drop = [
            k for k, v in column_mapping.items() 
            if k in df.columns and v in df.columns
        ]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            _LOGGER.info(f"Dropped duplicate source columns: {cols_to_drop}")
        
        if existing_renames:
            df = df.rename(columns=existing_renames)
            _LOGGER.info(f"Standardized column names: {list(existing_renames.keys())}")

        # Create target column as NEXT HOUR's demand (shift -1)
        # This matches the notebook experimentation where we predict future demand
        # Quote from notebook: "For the target, we will use the next hour bike count
        # because we want to predict what this value will be to adjust the pricing."
        if "demand" in df.columns:
            df["target"] = df["demand"].shift(-1)
            _LOGGER.info("Created 'target' column as next hour's demand (shift -1)")
        elif "cnt" in df.columns:
            df["target"] = df["cnt"].shift(-1)
            _LOGGER.info("Created 'target' column as next hour's cnt (shift -1)")
        else:
            _LOGGER.warning("No demand/cnt column found - 'target' column not created")

        # Fill NaN values at the end (last row has no next value)
        # Using forward fill as done in notebook: fillna(method='ffill')
        if "target" in df.columns:
            df["target"] = df["target"].ffill()

        # Create demand lags (using 'demand' column, NOT 'target')
        # CRITICAL: Notebook creates lags from 'cnt' (current hour data), not 'target' (next hour)
        # This matches the notebook logic:
        #   df['cnt_lag_1'] = df['cnt'].shift(1)  # 1 hour before current
        # Using 'target' would be semantically wrong since target = demand.shift(-1)
        demand_col = "demand" if "demand" in df.columns else None

        if demand_col:
            # Vectorized lag creation for better performance
            # Using demand_lag naming to match notebook's cnt_lag semantics
            for lag in lags:
                df[f"demand_lag{lag}"] = df[demand_col].shift(lag)
            _LOGGER.info(f"Created demand lag features: {[f'demand_lag{l}' for l in lags]}")

        # Create feature lags matching notebook experimentation
        # Notebook: for feat in lag_feats: for i in range(1, n+1): df[f'{feat}_lag_{i}'] = df[feat].shift(i)
        created_feature_lags = []
        for feature, lag_values in feature_lags.items():
            if feature in df.columns:
                for lag in lag_values:
                    col_name = f"{feature}_lag{lag}"
                    df[col_name] = df[feature].shift(lag)
                    created_feature_lags.append(col_name)
        
        if created_feature_lags:
            _LOGGER.info(f"Created {len(created_feature_lags)} feature lag columns: {created_feature_lags[:5]}...")

        # Optimize memory usage by downcasting numeric columns
        # Skip columns that can't be downcasted safely
        int_cols = df.select_dtypes(include=["int64"]).columns.tolist()
        for col in int_cols:
            try:
                df[col] = pd.to_numeric(df[col].values, downcast="integer")
            except (TypeError, ValueError):
                pass  # Skip columns that can't be downcasted

        float_cols = df.select_dtypes(include=["float64"]).columns.tolist()
        for col in float_cols:
            try:
                df[col] = pd.to_numeric(df[col].values, downcast="float")
            except (TypeError, ValueError):
                pass  # Skip columns that can't be downcasted

        # Create some basic interactions (only if columns are unique)
        if "hour" in df.columns and "day_of_week" in df.columns:
            hour_col = df["hour"]
            dow_col = df["day_of_week"]
            # Handle case where columns might be duplicated
            if isinstance(hour_col, pd.DataFrame):
                hour_col = hour_col.iloc[:, 0]
            if isinstance(dow_col, pd.DataFrame):
                dow_col = dow_col.iloc[:, 0]
            df["hour_day_interaction"] = hour_col.values * dow_col.values

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

        # Check for required columns (standardized names after feature engineering)
        required_base = ["target", "hour", "day_of_week"]
        missing = [col for col in required_base if col not in df.columns]

        if missing:
            _LOGGER.warning(f"Missing expected columns: {missing}")
            # Provide specific guidance for common issues
            if "target" in missing:
                _LOGGER.error(
                    "CRITICAL: 'target' column is missing. "
                    "Ensure create_feature_interactions() was called first."
                )

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


def split_features(
    df: pd.DataFrame,
    train_fraction: float = 0.8,
) -> dict[str, Any]:
    """Split validated features into train and test sets using TIME-BASED split.

    IMPORTANT: For time series data, we must preserve temporal order.
    The notebook uses: x_train, x_test = x[:train_size], x[train_size:]
    This ensures training data is BEFORE test data chronologically.

    Args:
        df: DataFrame with validated features including 'target' column
        train_fraction: Proportion of data for training (default 0.8)

    Returns:
        Dictionary with X_train, X_test, y_train, y_test DataFrames/Series
    """
    _LOGGER.info(f"Splitting features into train/test sets (train_fraction={train_fraction})...")

    try:
        # Ensure target column exists
        if "target" not in df.columns:
            raise ValueError("'target' column not found in DataFrame")

        # Separate features and target
        X = df.drop(columns=["target"])
        y = df["target"]

        # Remove any non-numeric columns that might cause issues
        non_numeric = X.select_dtypes(exclude=["number"]).columns.tolist()
        if non_numeric:
            _LOGGER.warning(f"Dropping non-numeric columns: {non_numeric}")
            X = X.select_dtypes(include=["number"])

        # TIME-BASED SPLIT (matching notebook approach)
        # Critical for time series: training data must be before test data
        # Notebook: train_size = int(train_fraction * df.shape[0])
        #           x_train, x_test = x[:train_size], x[train_size:]
        train_size = int(train_fraction * len(df))
        
        X_train = X.iloc[:train_size]
        X_test = X.iloc[train_size:]
        y_train = y.iloc[:train_size]
        y_test = y.iloc[train_size:]

        _LOGGER.info(
            f"TIME-BASED split complete. Train: {len(X_train)} samples, Test: {len(X_test)} samples"
        )
        _LOGGER.info(f"Features: {X_train.shape[1]} columns")

        # Convert Series to DataFrame for Parquet compatibility
        y_train_df = y_train.to_frame(name="target")
        y_test_df = y_test.to_frame(name="target")

        return {
            "X_train": X_train,
            "X_test": X_test,
            "y_train": y_train_df,
            "y_test": y_test_df,
        }

    except Exception as e:
        _LOGGER.error(f"Failed to split features: {e}")
        raise
