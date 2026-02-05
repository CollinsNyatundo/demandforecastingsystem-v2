"""
Centralized error handling and logging for demand forecasting system.

This module provides utilities for consistent error handling,
structured logging, and error tracking across the application.

Usage:
    from demand_forecasting.core.error_handler import ErrorHandler

    try:
        # Some operation
        result = process_data(df)
    except Exception as e:
        error_id = ErrorHandler.handle_pipeline_error(
            error=e,
            context={"stage": "preprocessing", "rows": len(df)},
            reraise=True
        )
"""

import logging
import traceback
from typing import Any
from uuid import uuid4

from demand_forecasting.core.exceptions import (
    ConfigurationError,
    DataQualityError,
    DataValidationError,
    DemandForecastingError,
    ModelServingError,
    ModelTrainingError,
    PipelineError,
)

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Centralized error handling with structured logging.

    Provides consistent error handling, categorization, and tracking
    across the demand forecasting system.
    """

    @staticmethod
    def handle_pipeline_error(
        error: Exception,
        context: dict[str, Any] | None = None,
        reraise: bool = True,
    ) -> str:
        """
        Handle pipeline errors with structured logging.

        Args:
            error: The exception that occurred
            context: Additional context (stage, data shapes, etc.)
            reraise: Whether to re-raise the exception

        Returns:
            Error ID for tracking

        Raises:
            Exception: Re-raises the original exception if reraise=True
        """
        error_id = str(uuid4())
        context = context or {}

        # Build structured log entry
        log_entry = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "stack_trace": traceback.format_exc(),
        }

        # Add exception-specific context
        if isinstance(error, DemandForecastingError):
            log_entry["error_code"] = error.error_code
            log_entry["exception_context"] = error.context
            log_entry["exception_timestamp"] = error.timestamp

        # Categorize and log with appropriate level
        if isinstance(error, (DataValidationError, DataQualityError)):
            logger.error(
                f"Data error [{error_id}]: {error}",
                extra={"structured_log": log_entry},
            )
        elif isinstance(error, ModelTrainingError):
            logger.error(
                f"Model training error [{error_id}]: {error}",
                extra={"structured_log": log_entry},
            )
        elif isinstance(error, ModelServingError):
            logger.error(
                f"Model serving error [{error_id}]: {error}",
                extra={"structured_log": log_entry},
            )
        elif isinstance(error, PipelineError):
            logger.error(
                f"Pipeline error [{error_id}]: {error}",
                extra={"structured_log": log_entry},
            )
        elif isinstance(error, ConfigurationError):
            logger.error(
                f"Configuration error [{error_id}]: {error}",
                extra={"structured_log": log_entry},
            )
        else:
            logger.critical(
                f"Unexpected error [{error_id}]: {error}",
                extra={"structured_log": log_entry},
            )

        if reraise:
            raise

        return error_id

    @staticmethod
    def wrap_with_context(
        error: Exception,
        context: dict[str, Any],
        error_class: type[DemandForecastingError] | None = None,
    ) -> DemandForecastingError:
        """
        Wrap an exception with additional context.

        Args:
            error: Original exception
            context: Context to add
            error_class: Optional specific error class to use

        Returns:
            Wrapped exception with context
        """
        if error_class is None:
            # Try to determine appropriate class from original error
            if isinstance(error, DemandForecastingError):
                error_class = type(error)
            else:
                error_class = DemandForecastingError

        # Merge existing context if present
        merged_context = {}
        if isinstance(error, DemandForecastingError):
            merged_context.update(error.context)
        merged_context.update(context)

        return error_class(str(error), context=merged_context)

    @staticmethod
    def format_error_response(
        error: Exception,
        include_trace: bool = False,
    ) -> dict[str, Any]:
        """
        Format an error for API response.

        Args:
            error: The exception to format
            include_trace: Whether to include stack trace (only for dev)

        Returns:
            Dictionary suitable for JSON response
        """
        error_id = str(uuid4())

        response = {
            "error": True,
            "error_id": error_id,
            "message": str(error),
            "type": type(error).__name__,
        }

        if isinstance(error, DemandForecastingError):
            response["error_code"] = error.error_code
            response["timestamp"] = error.timestamp
            # Only include safe context (no sensitive data)
            safe_context = {
                k: v
                for k, v in error.context.items()
                if k not in ("credentials", "api_key", "token", "password")
            }
            if safe_context:
                response["context"] = safe_context

        if include_trace:
            response["trace"] = traceback.format_exc()

        return response
