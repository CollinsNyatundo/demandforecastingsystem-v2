"""Custom exceptions for the demand forecasting system.

This module provides a hierarchy of exceptions for different failure modes,
following best practices for exception design:
- Specific exceptions for different failure types
- Include context in exception messages
- Support error tracking and monitoring

Exception Hierarchy:
    DemandForecastingError (base)
    ├── DataValidationError
    ├── DataQualityError
    ├── ModelTrainingError
    ├── ModelServingError
    ├── PipelineError
    └── ConfigurationError

Usage:
    from demand_forecasting.core.exceptions import DataValidationError

    try:
        validate_data(df)
    except DataValidationError as e:
        logger.error(f"Validation failed: {e}", extra={"context": e.context})
"""

from datetime import datetime
from typing import Any


class DemandForecastingError(Exception):
    """Base exception for all demand forecasting errors.

    Attributes:
        message: Human-readable error description
        context: Dictionary containing additional context about the error
        timestamp: ISO format timestamp when the error occurred
        error_code: Optional error code for categorization
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            context: Additional context about the error (e.g., data shapes, parameters)
            error_code: Optional error code for categorization
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.timestamp = datetime.utcnow().isoformat()
        self.error_code = error_code

    def __str__(self) -> str:
        """Return string representation with context."""
        base_msg = self.message
        if self.error_code:
            base_msg = f"[{self.error_code}] {base_msg}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base_msg = f"{base_msg} (context: {context_str})"
        return base_msg

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": type(self).__name__,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp,
            "error_code": self.error_code,
        }


class DataValidationError(DemandForecastingError):
    """Raised when data validation fails.

    Use this for schema validation failures, type mismatches,
    or constraint violations in input data.

    Examples:
        - Missing required columns
        - Invalid data types
        - Values outside expected ranges
        - Pandera schema validation failures
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        invalid_columns: list[str] | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        """Initialize DataValidationError.

        Args:
            message: Error description
            context: Additional context
            invalid_columns: List of columns that failed validation
            validation_errors: List of specific validation error messages
        """
        context = context or {}
        if invalid_columns:
            context["invalid_columns"] = invalid_columns
        if validation_errors:
            context["validation_errors"] = validation_errors
        super().__init__(message, context, error_code="DATA_VALIDATION")


class DataQualityError(DemandForecastingError):
    """Raised when data quality issues are detected.

    Use this for data quality problems that don't necessarily
    violate the schema but indicate potential issues.

    Examples:
        - High percentage of missing values
        - Unexpected distributions
        - Data drift detected
        - Duplicate records
        - Outliers beyond acceptable thresholds
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        quality_score: float | None = None,
        affected_columns: list[str] | None = None,
    ) -> None:
        """Initialize DataQualityError.

        Args:
            message: Error description
            context: Additional context
            quality_score: Overall quality score (0-1) if available
            affected_columns: Columns with quality issues
        """
        context = context or {}
        if quality_score is not None:
            context["quality_score"] = quality_score
        if affected_columns:
            context["affected_columns"] = affected_columns
        super().__init__(message, context, error_code="DATA_QUALITY")


class ModelTrainingError(DemandForecastingError):
    """Raised when model training fails.

    Use this for errors during the model training process.

    Examples:
        - Insufficient training data
        - Invalid hyperparameters
        - Convergence failures
        - Memory or resource exhaustion
        - Cross-validation failures
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        model_type: str | None = None,
        training_stage: str | None = None,
    ) -> None:
        """Initialize ModelTrainingError.

        Args:
            message: Error description
            context: Additional context
            model_type: Type of model being trained (e.g., "catboost", "random_forest")
            training_stage: Stage of training where error occurred
        """
        context = context or {}
        if model_type:
            context["model_type"] = model_type
        if training_stage:
            context["training_stage"] = training_stage
        super().__init__(message, context, error_code="MODEL_TRAINING")


class ModelServingError(DemandForecastingError):
    """Raised when model prediction/serving fails.

    Use this for errors during model inference.

    Examples:
        - Model not loaded
        - Invalid input features
        - Prediction timeout
        - Model version mismatch
        - Resource exhaustion during inference
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        model_version: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Initialize ModelServingError.

        Args:
            message: Error description
            context: Additional context
            model_version: Version of model that failed
            request_id: Request ID for tracing
        """
        context = context or {}
        if model_version:
            context["model_version"] = model_version
        if request_id:
            context["request_id"] = request_id
        super().__init__(message, context, error_code="MODEL_SERVING")


class PipelineError(DemandForecastingError):
    """Raised when Kedro pipeline execution fails.

    Use this for errors in pipeline orchestration.

    Examples:
        - Node execution failures
        - Missing pipeline inputs
        - Catalog errors
        - Pipeline configuration issues
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        pipeline_name: str | None = None,
        node_name: str | None = None,
    ) -> None:
        """Initialize PipelineError.

        Args:
            message: Error description
            context: Additional context
            pipeline_name: Name of pipeline that failed
            node_name: Name of node that failed
        """
        context = context or {}
        if pipeline_name:
            context["pipeline_name"] = pipeline_name
        if node_name:
            context["node_name"] = node_name
        super().__init__(message, context, error_code="PIPELINE")


class ConfigurationError(DemandForecastingError):
    """Raised when configuration is invalid or missing.

    Use this for configuration-related errors.

    Examples:
        - Missing required configuration keys
        - Invalid configuration values
        - Environment variable issues
        - File not found errors for config files
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        config_key: str | None = None,
        config_file: str | None = None,
    ) -> None:
        """Initialize ConfigurationError.

        Args:
            message: Error description
            context: Additional context
            config_key: Configuration key that caused the error
            config_file: Configuration file path if applicable
        """
        context = context or {}
        if config_key:
            context["config_key"] = config_key
        if config_file:
            context["config_file"] = config_file
        super().__init__(message, context, error_code="CONFIGURATION")
