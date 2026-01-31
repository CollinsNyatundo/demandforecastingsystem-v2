import pandas as pd
import pandera as pa
import logging
from pandera.typing import DataFrame
from .schemas import RawBikeDataSchema

logger = logging.getLogger(__name__)


def validate_etl_data(df: pd.DataFrame, stage_name: str) -> bool:
    """
    Validate data quality and size for ETL processing.
    
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
        logger.warning(f"Dataset has only {len(df)} samples, minimum recommended is {MIN_TRAINING_SAMPLES}")
    
    if len(df.columns) < MIN_FEATURE_COLUMNS:
        logger.warning(f"Dataset has only {len(df.columns)} columns, minimum recommended is {MIN_FEATURE_COLUMNS}")
    
    # Check for required columns
    required_cols = ['season', 'yr', 'mnth', 'hr', 'holiday', 'weekday', 
                    'workingday', 'weathersit', 'temp', 'atemp', 'hum', 
                    'windspeed', 'casual', 'registered', 'cnt']
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        logger.error(f"Missing required columns at {stage_name}: {missing_cols}")
        return False
    
    return True


@pa.check_types
def preprocess_data(df: DataFrame[RawBikeDataSchema]) -> pd.DataFrame:
    """
    Enhanced preprocessing with validation and graceful error handling.
    
    Args:
        df: Raw data validated against RawBikeDataSchema.
        
    Returns:
        Preprocessed data with [yr, casual, registered, datetime] dropped.
    """
    if not validate_etl_data(df, "preprocessing"):
        raise ValueError("Data validation failed in preprocessing")
    
    drop_cols = ['yr', 'casual', 'registered', 'datetime']
    # errors='ignore' ensures we don't crash if columns are missing (idempotency)
    return df.drop(columns=drop_cols, errors='ignore')
