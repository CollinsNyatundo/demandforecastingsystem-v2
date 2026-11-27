import logging

import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame

from .schemas import RawBikeDataSchema

logger = logging.getLogger(__name__)


_MAX_SKEWNESS_THRESHOLD = 2


def validate_etl_data(df: pd.DataFrame, stage_name: str) -> bool:  # noqa: C901, PLR0912
    """Validate data quality and size for ETL processing.

    Args:
        df: DataFrame to validate
        stage_name: Name of the ETL stage for logging

    Returns:
        True if validation passes, False otherwise
    """
    logger.info(f"Validating data at {stage_name} stage...")

    # Dataset size validation
    if len(df) == 0:
        logger.error(f"Empty dataframe at {stage_name} stage")
        return False

    # Minimum dataset size checks
    MIN_TRAINING_SAMPLES = 100
    MIN_FEATURE_COLUMNS = 5

    if len(df) < MIN_TRAINING_SAMPLES:
        logger.warning(
            f"Dataset has only {len(df)} samples, minimum recommended is {MIN_TRAINING_SAMPLES}"
        )

    if len(df.columns) < MIN_FEATURE_COLUMNS:
        logger.warning(
            f"Dataset has only {len(df.columns)} columns, minimum recommended is {MIN_FEATURE_COLUMNS}"
        )

    # Check for required columns
    required_cols = [
        "season",
        "yr",
        "mnth",
        "hr",
        "holiday",
        "weekday",
        "workingday",
        "weathersit",
        "temp",
        "atemp",
        "hum",
        "windspeed",
        "casual",
        "registered",
        "cnt",
    ]
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        logger.error(f"Missing required columns at {stage_name}: {missing_cols}")
        return False

    # Validate row count - ensure dataset is not empty
    if len(df) == 0:
        logger.error(f"Empty dataset detected at {stage_name}")
        return False

    if len(df) < MIN_TRAINING_SAMPLES:
        logger.warning(
            f"Dataset at {stage_name} has only {len(df)} rows. "
            "This may not be sufficient for reliable analysis."
        )

    # Validate temperature and humidity ranges (outlier detection)
    if "temp" in df.columns:
        # Temperature should be normalized (0-1 range typically)
        temp_min, temp_max = df["temp"].min(), df["temp"].max()
        if temp_max > 1.0 or temp_min < 0.0:
            logger.warning(
                f"Temperature values out of expected range [0, 1] at {stage_name}: "
                f"min={temp_min:.4f}, max={temp_max:.4f}"
            )

        # Check for outliers using IQR method
        Q1 = df["temp"].quantile(0.25)
        Q3 = df["temp"].quantile(0.75)
        IQR = Q3 - Q1
        outliers = df[(df["temp"] < (Q1 - 1.5 * IQR)) | (df["temp"] > (Q3 + 1.5 * IQR))]
        if len(outliers) > 0:
            logger.warning(
                f"Found {len(outliers)} temperature outliers at {stage_name} "
                f"({len(outliers) / len(df) * 100:.1f}% of data)"
            )

    if "hum" in df.columns:
        # Humidity should also be normalized (0-1 range)
        hum_min, hum_max = df["hum"].min(), df["hum"].max()
        if hum_max > 1.0 or hum_min < 0.0:
            logger.warning(
                f"Humidity values out of expected range [0, 1] at {stage_name}: "
                f"min={hum_min:.4f}, max={hum_max:.4f}"
            )

        # Check for outliers using IQR method
        Q1 = df["hum"].quantile(0.25)
        Q3 = df["hum"].quantile(0.75)
        IQR = Q3 - Q1
        outliers = df[(df["hum"] < (Q1 - 1.5 * IQR)) | (df["hum"] > (Q3 + 1.5 * IQR))]
        if len(outliers) > 0:
            logger.warning(
                f"Found {len(outliers)} humidity outliers at {stage_name} "
                f"({len(outliers) / len(df) * 100:.1f}% of data)"
            )

    # Basic distribution validation - check for extreme skewness
    numeric_cols = ["temp", "hum", "windspeed", "cnt"]
    for col in numeric_cols:
        if col in df.columns:
            skewness = df[col].skew()
            if abs(skewness) > _MAX_SKEWNESS_THRESHOLD:
                logger.warning(
                    f"Column '{col}' at {stage_name} has high skewness: {skewness:.2f}. "
                    "Consider transformation if this affects model performance."
                )

    return True


@pa.check_types
def preprocess_data(df: DataFrame[RawBikeDataSchema]) -> pd.DataFrame:
    """Preprocess data by dropping columns that are not needed for modeling.

    Based on ground truth from modeling notebook:
    - 'yr' does not help with predictions
    - 'casual', 'registered' are already included in target 'cnt'
    - 'datetime' is not needed for model features

    Args:
        df: Raw data validated against RawBikeDataSchema.

    Returns:
        Preprocessed data with [yr, casual, registered, datetime] dropped.

    Note:
        Function uses defensive programming approach - logs warnings for issues
        but continues processing with available data rather than failing fast.
    """
    # Validate data quality with defensive approach
    if not validate_etl_data(df, "preprocessing"):
        logger.warning(
            "Data validation issues detected in preprocessing. "
            "Proceeding with available data - this may affect model performance."
        )
        # Continue processing instead of failing fast

    # Drop columns as defined in modeling notebook
    drop_cols = ["yr", "casual", "registered", "datetime"]

    # Check which columns exist before dropping
    existing_cols = [col for col in drop_cols if col in df.columns]
    missing_cols = set(drop_cols) - set(existing_cols)

    if missing_cols:
        logger.warning(
            f"Expected columns not present for dropping: {missing_cols}. "
            f"This may indicate upstream pipeline changes."
        )

    # Explicit dropping - fail if unexpected behavior
    result = df.drop(columns=existing_cols)

    # Audit log - essential for demand forecasting ML systems
    logger.info(
        f"Preprocessing complete. Dropped {len(existing_cols)} columns: {existing_cols}. "
        f"Output shape: {result.shape}. Missing columns: {missing_cols}"
    )

    # Validate that expected columns remain after preprocessing
    expected_remaining_cols = [
        "season",
        "mnth",
        "hr",
        "holiday",
        "weekday",
        "workingday",
        "weathersit",
        "temp",
        "atemp",
        "hum",
        "windspeed",
        "cnt",
    ]
    remaining_missing = set(expected_remaining_cols) - set(result.columns)
    if remaining_missing:
        logger.error(
            f"Critical columns missing after preprocessing: {remaining_missing}"
        )
        logger.warning(
            "Proceeding with available data - model performance may be severely impacted"
        )

    return result
