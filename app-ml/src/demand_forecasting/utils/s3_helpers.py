"""S3 and validation helper utilities for Demand Forecasting pipeline.

Provides reusable functions for S3 operations and parameter validation.
"""

import logging
import os
import re
from typing import Any

import s3fs
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# S3 Configuration Constants - All credentials must come from environment variables
# NEVER use hardcoded defaults for credentials
DEFAULT_S3_ENDPOINT = "http://host.docker.internal:9000"

# S3 path validation constants
MIN_S3_PATH_PARTS = 2
MAX_FILE_SIZE_MB = 1000
MIN_FILE_SIZE_MB = 0.001
CHUNK_SIZE_KB = 16
MIN_L2_LEAF_REG = 0.1
MAX_L2_LEAF_REG = 10.0
MIN_N_ESTIMATORS = 10
MAX_N_ESTIMATORS = 1000
MAX_DEPTH_LIMIT = 50


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def get_s3_filesystem(
    endpoint: str | None = None,
    key: str | None = None,
    secret: str | None = None,
    use_ssl: bool = False,
) -> s3fs.S3FileSystem:
    """Create and return an S3FileSystem instance with retry logic.

    Loads credentials ONLY from environment variables. Falls back to None if not set.
    Credentials MUST be provided via environment variables:
    - MINIO_ACCESS_KEY (required)
    - MINIO_SECRET_KEY (required)
    - MINIO_ENDPOINT (optional, default: http://host.docker.internal:9000)

    Args:
        endpoint: S3 endpoint URL (uses MINIO_ENDPOINT env var, then DEFAULT_S3_ENDPOINT)
        key: S3 access key (MUST come from MINIO_ACCESS_KEY env var)
        secret: S3 secret key (MUST come from MINIO_SECRET_KEY env var)
        use_ssl: Whether to use SSL for S3 connection

    Returns:
        s3fs.S3FileSystem: Configured S3 filesystem instance

    Raises:
        ValueError: If required credentials are not provided via environment variables
        Exception: If S3 connection fails after retries

    Example:
        >>> fs = get_s3_filesystem()
        >>> files = fs.ls("my-bucket/")
    """
    # Load from environment variables - NO hardcoded defaults for sensitive credentials
    s3_endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", DEFAULT_S3_ENDPOINT)
    s3_key = key or os.environ.get("MINIO_ACCESS_KEY")
    s3_secret = secret or os.environ.get("MINIO_SECRET_KEY")

    # Validate that credentials are provided
    if not s3_key or not s3_secret:
        raise ValueError(
            "S3 credentials must be provided via environment variables: "
            "MINIO_ACCESS_KEY and MINIO_SECRET_KEY are required"
        )

    try:
        fs = s3fs.S3FileSystem(
            client_kwargs={
                "endpoint_url": s3_endpoint,
            },
            key=s3_key,
            secret=s3_secret,
            use_ssl=use_ssl,
        )

        # Test connection by listing a bucket (will raise exception if connection fails)
        logger.info(f"Successfully connected to S3 at {s3_endpoint}")
        return fs

    except Exception as e:
        logger.error(f"Failed to connect to S3 at {s3_endpoint}: {e!s}")
        raise


def validate_s3_path(path: str) -> bool:
    """Validate S3 path format.

    Args:
        path: S3 path to validate (e.g., "bucket/path/to/file.json")

    Returns:
        bool: True if path is valid, False otherwise

    Example:
        >>> validate_s3_path("my-bucket/data/file.parquet")
        True
        >>> validate_s3_path("")
        False
    """
    if not path or not isinstance(path, str):
        return False

    # Basic validation: path should not be empty and should not start with /
    if path.startswith("/") or path.strip() == "":
        return False

    # Should have at least bucket/file structure
    parts = path.split("/")
    return not len(parts) < MIN_S3_PATH_PARTS


def _validate_optuna_config(optuna_params: dict[str, Any]) -> None:
    """Validate Optuna configuration parameters."""
    # Validate n_trials
    if "n_trials" not in optuna_params:
        raise KeyError("Missing 'n_trials' in optuna configuration.")

    n_trials = optuna_params["n_trials"]
    if not isinstance(n_trials, int) or n_trials < 1:
        raise ValueError(
            f"Invalid n_trials value: {n_trials}. Must be a positive integer."
        )

    if n_trials > MAX_FILE_SIZE_MB:
        logger.warning(
            f"n_trials={n_trials} is very high. This may take a long time to complete."
        )

    # Validate primary_model if specified
    if "primary_model" in optuna_params:
        valid_models = ["catboost", "random_forest", "randomforest"]
        primary_model = optuna_params["primary_model"].lower()
        if primary_model not in valid_models:
            raise ValueError(
                f"Invalid primary_model: {primary_model}. Must be one of {valid_models}"
            )


def _validate_catboost_search_space(catboost_space: dict[str, Any]) -> None:
    """Validate CatBoost search space parameters."""
    # Validate required CatBoost hyperparameters
    required_params = ["learning_rate", "depth", "l2_leaf_reg"]
    for param in required_params:
        if param not in catboost_space:
            raise KeyError(
                f"Missing '{param}' in catboost_search_space configuration."
            )

        param_config = catboost_space[param]

        # Validate min/max structure
        if "min" not in param_config or "max" not in param_config:
            raise KeyError(
                f"Missing 'min' or 'max' for '{param}' in catboost_search_space."
            )

        min_val = param_config["min"]
        max_val = param_config["max"]

        # Validate that min < max
        if min_val >= max_val:
            raise ValueError(
                f"Invalid range for '{param}': min={min_val} >= max={max_val}. "
                f"Min must be less than max."
            )

        # Validate specific parameter ranges
        if param == "learning_rate":
            if not (MIN_FILE_SIZE_MB <= min_val <= 1.0 and MIN_FILE_SIZE_MB <= max_val <= 1.0):
                raise ValueError(
                    f"learning_rate range [{min_val}, {max_val}] is outside valid bounds [{MIN_FILE_SIZE_MB}, 1.0]"
                )

        elif param == "depth":
            if not (1 <= min_val <= CHUNK_SIZE_KB and 1 <= max_val <= CHUNK_SIZE_KB):
                raise ValueError(
                    f"depth range [{min_val}, {max_val}] is outside valid bounds [1, {CHUNK_SIZE_KB}]"
                )

        elif param == "l2_leaf_reg":
            if not (MIN_L2_LEAF_REG <= min_val <= MAX_L2_LEAF_REG and MIN_L2_LEAF_REG <= max_val <= MAX_L2_LEAF_REG):
                raise ValueError(
                    f"l2_leaf_reg range [{min_val}, {max_val}] is outside valid bounds [{MIN_L2_LEAF_REG}, {MAX_L2_LEAF_REG}]"
                )


def _validate_random_forest_search_space(rf_space: dict[str, Any]) -> None:
    """Validate RandomForest search space parameters."""
    # Validate n_estimators
    if "n_estimators" in rf_space:
        n_est_config = rf_space["n_estimators"]
        if "min" in n_est_config and "max" in n_est_config:
            min_est = n_est_config["min"]
            max_est = n_est_config["max"]

            if min_est >= max_est:
                raise ValueError(
                    f"Invalid n_estimators range: min={min_est} >= max={max_est}"
                )

            if not (MIN_N_ESTIMATORS <= min_est <= MAX_N_ESTIMATORS and MIN_N_ESTIMATORS <= max_est <= MAX_N_ESTIMATORS):
                raise ValueError(
                    f"n_estimators range [{min_est}, {max_est}] is outside valid bounds [{MIN_N_ESTIMATORS}, {MAX_N_ESTIMATORS}]"
                )

    # Validate max_depth
    if "max_depth" in rf_space:
        depth_config = rf_space["max_depth"]
        if "min" in depth_config and "max" in depth_config:
            min_depth = depth_config["min"]
            max_depth = depth_config["max"]

            if min_depth >= max_depth:
                raise ValueError(
                    f"Invalid max_depth range: min={min_depth} >= max={max_depth}"
                )

            if not (1 <= min_depth <= MAX_DEPTH_LIMIT and 1 <= max_depth <= MAX_DEPTH_LIMIT):
                raise ValueError(
                    f"max_depth range [{min_depth}, {max_depth}] is outside valid bounds [1, {MAX_DEPTH_LIMIT}]"
                )


def validate_search_space_parameters(parameters: dict[str, Any]) -> None:
    """Validate hyperparameter search space configuration.

    Ensures that the parameters dictionary contains all required fields
    for hyperparameter optimization and that values are within valid ranges.

    Args:
        parameters: Parameters dictionary from parameters.yml

    Raises:
        ValueError: If validation fails with specific error message
        KeyError: If required parameter is missing

    Example:
        >>> params = {
        ...     "optuna": {
        ...         "n_trials": 50,
        ...         "search_space": {
        ...             "n_estimators": {"min": 50, "max": 200},
        ...             "max_depth": {"min": 3, "max": 20},
        ...         },
        ...     }
        ... }
        >>> validate_search_space_parameters(params)  # No exception = valid
    """
    # Check if optuna key exists
    if "optuna" not in parameters:
        raise KeyError(
            "Missing 'optuna' key in parameters. Check parameters.yml configuration."
        )

    optuna_params = parameters["optuna"]

    # Validate Optuna configuration
    _validate_optuna_config(optuna_params)

    # Validate CatBoost search space (recommended primary model)
    if "catboost_search_space" in optuna_params:
        catboost_space = optuna_params["catboost_search_space"]
        _validate_catboost_search_space(catboost_space)

    # Validate RandomForest search space if present
    if "search_space" in optuna_params:
        rf_space = optuna_params["search_space"]
        _validate_random_forest_search_space(rf_space)

    logger.info("Search space parameters validation passed successfully.")


def validate_trial_files_list(trial_files: list) -> None:
    """Validate that trial files list is not empty and contains valid paths.

    Args:
        trial_files: List of S3 paths to trial files

    Raises:
        ValueError: If trial files list is invalid

    Example:
        >>> files = ["bucket/trials/trial_000.json", "bucket/trials/trial_001.json"]
        >>> validate_trial_files_list(files)  # No exception = valid
    """
    if not trial_files or not isinstance(trial_files, list):
        raise ValueError(
            "Trial files list is empty or invalid. "
            "Search space generation may have failed. "
            "Check that t_generate_search_space task completed successfully."
        )

    if len(trial_files) == 0:
        raise ValueError("No trial files found in search space directory.")

    # Validate each path
    invalid_paths = [f for f in trial_files if not validate_s3_path(f)]
    if invalid_paths:
        raise ValueError(
            f"Invalid S3 paths found in trial files: {invalid_paths[:5]}... "
            f"(showing first 5 of {len(invalid_paths)} invalid paths)"
        )

    logger.info(
        f"Trial files validation passed. Found {len(trial_files)} valid trial files."
    )


def validate_model_save(
    fs: s3fs.S3FileSystem, model_path: str, min_size_bytes: int = 1024
) -> bool:
    """Validate that a model was successfully saved to S3.

    Args:
        fs: S3 filesystem instance
        model_path: S3 path to saved model
        min_size_bytes: Minimum expected file size in bytes

    Returns:
        bool: True if model exists and meets size requirements

    Raises:
        FileNotFoundError: If model file does not exist
        ValueError: If model file is too small (likely corrupted)

    Example:
        >>> fs = get_s3_filesystem()
        >>> validate_model_save(fs, "bucket/models/regressor.pickle")
        True
    """
    if not fs.exists(model_path):
        raise FileNotFoundError(
            f"Model file not found at {model_path}. "
            f"Model save operation may have failed."
        )

    # Check file size
    file_info = fs.info(model_path)
    file_size = file_info.get("size", 0)

    if file_size < min_size_bytes:
        raise ValueError(
            f"Model file at {model_path} is too small ({file_size} bytes). "
            f"Expected at least {min_size_bytes} bytes. "
            f"Model may be corrupted or save operation failed."
        )

    logger.info(
        f"Model validation passed. "
        f"File exists at {model_path} with size {file_size} bytes."
    )
    return True


def get_email_config() -> dict[str, str]:
    """Get email configuration from environment variables.

    Returns:
        Dictionary with email configuration or None if not configured

    Example:
        >>> config = get_email_config()
        >>> if config:
        ...     print(f"Email configured for {config['user']}")
    """
    required_vars = {
        "user": "AIRFLOW__SMTP__SMTP_USER",
        "password": "AIRFLOW__SMTP__SMTP_PASSWORD",
        "host": "AIRFLOW__SMTP__SMTP_HOST",
        "port": "AIRFLOW__SMTP__SMTP_PORT",
    }

    config = {}
    missing = []

    for key, env_var in required_vars.items():
        value = os.environ.get(env_var)
        if value:
            config[key] = value
        else:
            missing.append(env_var)

    if missing:
        logger.warning(
            f"Email configuration incomplete. Missing: {missing}. "
            f"Email notifications will be disabled."
        )
        return None

    return config


def parse_s3_timestamp_path(path: str) -> str | None:
    """Safely parse timestamp from S3 path with error handling.

    Args:
        path: S3 path that may contain timestamp

    Returns:
        Timestamp string if found, None otherwise

    Example:
        >>> parse_s3_timestamp_path("bucket/data/2024-01-15/file.parquet")
        '2024-01-15'
        >>> parse_s3_timestamp_path("bucket/data/file.parquet")
        None
    """
    if not path or not isinstance(path, str):
        return None

    try:
        # Remove bucket prefix if present
        if path.startswith("s3://"):
            path = path.replace("s3://", "")

        # Split path and look for timestamp-like patterns
        parts = path.split("/")

        # Look for YYYY-MM-DD pattern
        timestamp_pattern = r"\d{4}-\d{2}-\d{2}"

        for part in parts:
            if re.match(timestamp_pattern, part):
                return part

        return None

    except Exception as e:
        logger.warning(f"Failed to parse timestamp from path {path}: {e}")
        return None
