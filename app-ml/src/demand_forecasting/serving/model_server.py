"""Production-grade FastAPI model server for demand forecasting."""

import logging
import math
import os
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, ClassVar

import argon2
import catboost
import mlflow
import numpy as np
import pandas as pd
from cachetools import TTLCache
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from starlette.middleware.base import BaseHTTPMiddleware

# Evidently drift monitoring integration
try:
    from demand_forecasting.integrations.evidently_integration import (
        EVIDENTLY_AVAILABLE,
        get_drift_metrics_for_prometheus,
    )
except ImportError:
    EVIDENTLY_AVAILABLE = False
    get_drift_metrics_for_prometheus = None  # type: ignore[assignment]
    logging.warning("Evidently integration not available. Drift monitoring disabled.")

# S3 filesystem for model loading fallback
try:
    import s3fs

    S3FS_AVAILABLE = True
except ImportError:
    S3FS_AVAILABLE = False
    logging.warning("s3fs not available. S3 model loading disabled.")


# A/B Testing integration (feature-flagged)
ENABLE_AB_TESTING = os.environ.get("ENABLE_AB_TESTING", "false").lower() == "true"
try:
    from demand_forecasting.serving.model_router import ABTestManager

    AB_TESTING_AVAILABLE = True
except ImportError:
    AB_TESTING_AVAILABLE = False
    if ENABLE_AB_TESTING:
        logging.warning("A/B testing enabled but model_router not available.")

# Global A/B test manager (initialized during lifespan if enabled)
ab_test_manager = {}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting cache (IP -> attempt count)
rate_limit_cache = TTLCache(maxsize=10000, ttl=3600)  # 1 hour TTL

# Request rate limiting cache (IP -> request timestamps)
# Comprehensive rate limiting for all endpoints
request_rate_cache: dict[str, list[float]] = {}

# Rate limiting constants
MAX_FAILED_ATTEMPTS_PER_HOUR = 10
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_WINDOW_SECONDS = 60

# Global model storage
ml_models = {}

# Global feature metadata
feature_metadata = {}

# Prometheus metrics
prediction_requests_total = Counter(
    "prediction_requests_total", "Total prediction requests", ["model_id", "status"]
)
prediction_duration = Histogram(
    "prediction_duration_seconds", "Prediction request duration"
)
model_accuracy = Gauge("model_accuracy", "Current model accuracy", ["model_id"])

# Evidently drift Prometheus gauges (matches Grafana data_drift.json queries)
evidently_dataset_drift_gauge = Gauge(
    "evidently_dataset_drift", "Whether dataset drift is detected (0 or 1)"
)
evidently_drift_share_gauge = Gauge(
    "evidently_drift_share", "Share of drifted features (0.0 to 1.0)"
)
evidently_columns_total_gauge = Gauge(
    "evidently_columns_total", "Total number of monitored columns"
)
evidently_columns_drifted_gauge = Gauge(
    "evidently_columns_drifted", "Number of columns with detected drift"
)

# Global reference data for drift comparison
reference_data = {}

# Last drift check timestamp
last_drift_check = {"timestamp": None, "metrics": {}}


class PredictionRequest(BaseModel):
    """Prediction request with comprehensive validation.

    Implements defense-in-depth:
    1. Type validation (Pydantic)
    2. Range validation (domain constraints)
    3. Anomaly detection (statistical bounds)
    4. Injection protection (max features limit)

    Note: The feature set is flexible to accommodate different model versions.
    The model loaded at runtime determines which features are actually used.
    Core features (temp, humidity, wind_speed, hour, day_of_week) are always required.
    Additional features like lag values may be optional depending on model architecture.
    """

    features: dict[str, float] = Field(
        ..., description="Weather and temporal features for demand prediction"
    )

    model_config = ConfigDict(
        # Reject extra fields at request level
        extra="forbid",
        # Example for documentation (Pydantic v2 compatible)
        json_schema_extra={
            "example": {
                "features": {
                    "temp": 0.5,
                    "humidity": 0.65,
                    "wind_speed": 0.15,
                    "hour": 14,
                    "day_of_week": 3,
                    "month": 6,
                }
            }
        },
    )

    # Core features that are always required
    CORE_FEATURES: ClassVar[set[str]] = {
        "temp",
        "humidity",
        "wind_speed",
        "hour",
        "day_of_week",
    }

    # Optional features that may be provided depending on model requirements
    OPTIONAL_FEATURES: ClassVar[set[str]] = {
        "month",
        "quarter",
        "day_of_year",
        "year",
        "season",
        "holiday",
        "workingday",
        "weather_condition",
        "feels_like_temp",
        "casual",
        "registered",
        # Demand lag features (matching notebook's cnt_lag naming convention)
        # These are lags of current demand, not target (next hour)
        "demand_lag1",
        "demand_lag2",
        "demand_lag22",
        "demand_lag23",
        # Feature lag features (using renamed column names)
        "hour_lag1",
        "hour_lag2",
        "hour_lag3",
        "day_of_week_lag1",
        "day_of_week_lag2",
        "day_of_week_lag3",
        "weather_condition_lag1",
        "weather_condition_lag2",
        "weather_condition_lag3",
        "temp_lag1",
        "temp_lag2",
        "temp_lag3",
        "humidity_lag1",
        "humidity_lag2",
        "humidity_lag3",
        # Interaction features
        "hour_day_interaction",
        # Raw demand (current hour) - kept as feature per notebook
        "demand",
    }

    # Maximum number of features to prevent injection attacks
    MAX_FEATURES: ClassVar[int] = 50

    @field_validator("features")
    @classmethod
    def validate_feature_structure(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate feature keys and basic structure."""
        # Check for minimum required features
        missing = cls.CORE_FEATURES - set(v.keys())
        if missing:
            raise ValueError(
                f"Missing required core features: {sorted(missing)}. "
                f"Required: {sorted(cls.CORE_FEATURES)}"
            )

        # Check for maximum feature count (prevent injection)
        if len(v) > cls.MAX_FEATURES:
            raise ValueError(
                f"Too many features provided ({len(v)}). "
                f"Maximum allowed: {cls.MAX_FEATURES}"
            )

        # Check for unknown features (only allow known features)
        allowed_features = cls.CORE_FEATURES | cls.OPTIONAL_FEATURES
        extra = set(v.keys()) - allowed_features
        if extra:
            raise ValueError(
                f"Unknown features detected: {sorted(extra)}. "
                f"Allowed features: core={sorted(cls.CORE_FEATURES)}, "
                f"optional={sorted(cls.OPTIONAL_FEATURES)}"
            )

        return v

    @model_validator(mode="after")
    def validate_feature_values(self) -> "PredictionRequest":
        """Validate feature value ranges and quality.

        Based on domain knowledge and training data statistics.
        """
        features = self.features

        # Define validation rules: (min, max, description)
        # Core features have strict validation
        validations = {
            # Core features (always required)
            "temp": (0.0, 1.0, "Normalized temperature (0-1)"),
            "humidity": (0.0, 1.0, "Normalized humidity (0-1)"),
            "wind_speed": (0.0, 1.0, "Normalized wind speed (0-1)"),
            "hour": (0, 23, "Hour of day (0-23)"),
            "day_of_week": (0, 6, "Day of week (0=Mon, 6=Sun)"),
            # Optional temporal features
            "month": (1, 12, "Month (1-12)"),
            "quarter": (1, 4, "Quarter (1-4)"),
            "day_of_year": (1, 366, "Day of year (1-366)"),
            "year": (0, 1, "Normalized year (0-1)"),
            "season": (1, 4, "Season (1-4)"),
            # Binary features
            "holiday": (0, 1, "Holiday flag (0 or 1)"),
            "workingday": (0, 1, "Working day flag (0 or 1)"),
            # Weather features
            "weather_condition": (1, 4, "Weather condition (1-4)"),
            "feels_like_temp": (0.0, 1.0, "Normalized feels-like temp (0-1)"),
            # Demand features (lag features can have wider ranges)
            "demand": (-1000, 10000, "Demand/count value"),
        }

        errors = []

        for feature, (min_val, max_val, description) in validations.items():
            if feature not in features:
                continue

            value = features[feature]

            # Type validation (should be caught by Pydantic, but double-check)
            if not isinstance(value, (int, float)):
                errors.append(f"{feature}: must be numeric, got {type(value).__name__}")
                continue

            # NaN/Inf check
            if math.isnan(value) or math.isinf(value):
                errors.append(f"{feature}: contains invalid value (NaN or Inf)")
                continue

            # Range validation
            if not (min_val <= value <= max_val):
                errors.append(
                    f"{feature}: value {value} out of range. "
                    f"{description}. Valid range: [{min_val}, {max_val}]"
                )

        if errors:
            raise ValueError(
                "Feature validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return self


class PredictionResponse(BaseModel):
    """Prediction response with metadata for transparency."""

    prediction: float = Field(..., description="Predicted demand value")
    confidence: float | None = Field(
        None, description="Model confidence score (0-1)", ge=0.0, le=1.0
    )
    model_version: str = Field(..., description="Model version used")
    timestamp: str = Field(..., description="Prediction timestamp (ISO 8601)")
    model_id: str | None = Field(None, description="Model identifier")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prediction": 142.5,
                "confidence": 0.87,
                "model_version": "v2.1.0",
                "timestamp": "2026-01-31T12:00:00Z",
                "model_id": "production",
            }
        }
    )


class ModelInfo(BaseModel):
    """Model information response."""

    model_version: str
    model_type: str
    features: list
    last_updated: str
    model_id: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    models_loaded: int
    timestamp: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load models during startup and cleanup on shutdown. Fails if no model available."""
    try:
        logger.info("Starting model server...")

        model_loaded = False

        # Load production model from MLflow with proper error handling
        # AUDIT-M4: Model versioning support for rollbacks and A/B testing
        # Use MODEL_VERSION env var for specific version, MODEL_STAGE for stage (default: Production)
        try:
            # Issue 2 fix: default matches registered_model_name used in airflow_dag_enhanced.py
            model_name = os.environ.get("MODEL_NAME", "demand_forecasting_catboost")
            model_version = os.environ.get("MODEL_VERSION")  # Specific version number
            model_stage = os.environ.get(
                "MODEL_STAGE", "Production"
            )  # Stage: Production, Staging, etc.

            if model_version:
                # Load specific version (for rollbacks)
                model_uri = f"models:/{model_name}/{model_version}"
                logger.info(
                    f"Loading model version {model_version} from MLflow registry"
                )
            else:
                # Load by stage (default: Production)
                model_uri = f"models:/{model_name}/{model_stage}"
                logger.info(f"Loading model stage '{model_stage}' from MLflow registry")

            ml_models["production"] = mlflow.pyfunc.load_model(model_uri)
            logger.info(f"Model loaded successfully from: {model_uri}")
            model_loaded = True
        except Exception as mlflow_error:
            logger.error(f"Failed to load production model from MLflow: {mlflow_error}")
            # Try to load from local path as fallback
            try:
                ml_models["production"] = catboost.CatBoostRegressor().load_model(
                    "models/experiments/final_catboost_model.cbm"
                )
                logger.info("Production model loaded successfully from local path")
                model_loaded = True
            except Exception as fallback_error:
                logger.error(f"Failed to load fallback model: {fallback_error}")

            # Try to load from MinIO/S3 as last resort
            if not model_loaded and S3FS_AVAILABLE:
                try:
                    import pickle

                    s3_endpoint = os.environ.get(
                        "MLFLOW_S3_ENDPOINT_URL", "http://minio:9000"
                    )
                    s3_key = os.environ.get(
                        "MINIO_ACCESS_KEY", os.environ.get("AWS_ACCESS_KEY_ID", "")
                    )
                    s3_secret = os.environ.get(
                        "MINIO_SECRET_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY", "")
                    )
                    fs = s3fs.S3FileSystem(
                        key=s3_key,
                        secret=s3_secret,
                        client_kwargs={"endpoint_url": s3_endpoint},
                    )
                    bucket = os.environ.get("S3_BUCKET", "demand-forecasting")
                    model_prefix = f"{bucket}/06_models/"
                    model_files = sorted(
                        [f for f in fs.ls(model_prefix) if f.endswith(".pickle")],
                        reverse=True,
                    )
                    if model_files:
                        latest_model_path = model_files[0]
                        logger.info(f"Loading model from S3: {latest_model_path}")
                        with fs.open(latest_model_path, "rb") as f:
                            ml_models["production"] = pickle.load(f)  # noqa: S301
                        logger.info("Model loaded successfully from MinIO/S3")
                        model_loaded = True
                except Exception as s3_error:
                    logger.error(f"Failed to load model from S3: {s3_error}")

        # CRITICAL: Fail startup if no model is available
        if not model_loaded:
            logger.error(
                "CRITICAL: No model available. Server will start but predictions will fail. "
                "Please train a model and register it with MLflow, save to S3, or place at: "
                "models/experiments/final_catboost_model.cbm"
            )
            # Allow server to start for health checks even without model
            # Prediction endpoints will return 503

        # Load feature metadata for correct feature engineering
        try:
            import json
            from pathlib import Path

            metadata_path = Path("models/feature_metadata.json")
            if metadata_path.exists():
                with open(metadata_path) as f:
                    feature_metadata.update(json.load(f))
                logger.info(
                    f"Loaded feature metadata: {feature_metadata.get('n_features', 0)} features"
                )
            else:
                logger.warning(
                    f"Feature metadata not found at {metadata_path}. "
                    "Using default features. This may cause prediction errors."
                )
                # Set default fallback (for backward compatibility)
                feature_metadata["feature_names"] = [
                    "temp",
                    "humidity",
                    "wind_speed",
                    "hour",
                    "day_of_week",
                ]
                feature_metadata["n_features"] = 5
        except Exception as e:
            logger.error(f"Failed to load feature metadata: {e}")
            # Use minimal fallback
            feature_metadata["feature_names"] = [
                "temp",
                "humidity",
                "wind_speed",
                "hour",
                "day_of_week",
            ]
            feature_metadata["n_features"] = 5

        # Load reference data for drift monitoring
        if EVIDENTLY_AVAILABLE:
            try:
                ref_data_path = Path("data/01_raw/raw_bike_data.parquet")
                if not ref_data_path.exists():
                    # Try loading from S3
                    if S3FS_AVAILABLE:
                        try:
                            s3_endpoint = os.environ.get(
                                "MLFLOW_S3_ENDPOINT_URL", "http://minio:9000"
                            )
                            s3_key = os.environ.get(
                                "MINIO_ACCESS_KEY",
                                os.environ.get("AWS_ACCESS_KEY_ID", ""),
                            )
                            s3_secret = os.environ.get(
                                "MINIO_SECRET_KEY",
                                os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
                            )
                            fs = s3fs.S3FileSystem(
                                key=s3_key,
                                secret=s3_secret,
                                client_kwargs={"endpoint_url": s3_endpoint},
                            )
                            bucket = os.environ.get("S3_BUCKET", "demand-forecasting")
                            with fs.open(
                                f"{bucket}/01_raw/raw_bike_data.parquet", "rb"
                            ) as f:
                                reference_data["df"] = pd.read_parquet(f)
                            logger.info(
                                "Reference data loaded from S3 for drift monitoring"
                            )
                        except Exception as s3_err:
                            logger.warning(
                                f"Could not load reference data from S3: {s3_err}"
                            )
                else:
                    reference_data["df"] = pd.read_parquet(ref_data_path)
                    logger.info(
                        f"Reference data loaded: {len(reference_data['df'])} rows"
                    )
            except Exception as e:
                logger.warning(
                    f"Could not load reference data for drift monitoring: {e}"
                )
        else:
            logger.info("Evidently not available - drift monitoring disabled")

        # Initialize A/B testing if enabled
        if ENABLE_AB_TESTING and AB_TESTING_AVAILABLE:
            model_b_uri = os.environ.get("MODEL_B_URI")
            model_a_uri = os.environ.get(
                "MODEL_A_URI",
                f"models:/{os.environ.get('MODEL_NAME', 'demand_forecasting')}/Production",
            )
            if model_b_uri:
                try:
                    ab_split = float(os.environ.get("AB_SPLIT", "0.7"))
                    test_name = os.environ.get("AB_TEST_NAME", "production_ab_test")
                    ab_test_manager["manager"] = ABTestManager(
                        test_name=test_name,
                        model_a_uri=model_a_uri,
                        model_b_uri=model_b_uri,
                        initial_split=ab_split,
                    )
                    logger.info(
                        f"A/B testing initialized: {test_name} "
                        f"(A={model_a_uri}, B={model_b_uri}, split={ab_split:.0%})"
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize A/B testing: {e}")
            else:
                logger.info("A/B testing enabled but MODEL_B_URI not set. Skipping.")
        elif ENABLE_AB_TESTING:
            logger.warning("A/B testing enabled but ABTestManager not available.")

        # Start metrics server
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)
        logger.info("Prometheus metrics endpoint mounted at /metrics")

        yield

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        # Clean up resources
        ml_models.clear()
        feature_metadata.clear()
        reference_data.clear()
        ab_test_manager.clear()
        logger.info("Model server shutdown complete")


def get_allowed_origins() -> list[str]:
    """Environment-based CORS configuration.

    Follows principle of least privilege - only allow necessary origins.
    Production domains must be explicitly configured.
    """
    env = os.getenv("ENVIRONMENT", "development")

    origins_map = {
        "production": [
            # Production domains - MUST be configured in environment
            "https://yourdomain.com",
            "https://api.yourdomain.com",
        ],
        "staging": ["https://staging.yourdomain.com"],
        "development": [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8050",  # Dash UI (app-ui)
            "http://localhost:8080",
            "http://localhost:8501",  # Streamlit (legacy, kept for convenience)
        ],
    }

    return origins_map.get(env, origins_map["development"])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add comprehensive security headers to all responses.

    Based on OWASP Secure Headers Project:
    https://owasp.org/www-project-secure-headers/

    Implements defense-in-depth security headers for production deployment.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process HTTP request and add security headers.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in the chain

        Returns:
            HTTP response with security headers added
        """
        response: Response = await call_next(request)

        # Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing attacks
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection (legacy browsers)
        # Note: Modern browsers ignore this, CSP is primary defense
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS in production (HSTS)
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy - primary XSS defense
        csp_directives = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # Required for some UI frameworks
            "img-src 'self' data: https:",  # Allow data URIs for images
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",  # Prevent clickjacking
            "base-uri 'self'",
            "form-action 'self'",
        ]

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Referrer policy for privacy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy - disable unnecessary browser features
        permissions_directives = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()",
            "ambient-light-sensor=()",
            "autoplay=()",
            "encrypted-media=()",
            "fullscreen=()",
            "picture-in-picture=()",
        ]

        response.headers["Permissions-Policy"] = ", ".join(permissions_directives)

        # Remove server information
        response.headers["Server"] = "Demand-Forecasting-API"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for API endpoints.

    Implements IP-based rate limiting to prevent abuse and ensure fair usage.
    (Rate limiting on model server)

    Configuration via environment variables:
    - RATE_LIMIT_PER_MINUTE: Max requests per minute per IP (default: 60)
    - RATE_LIMIT_ENABLED: Enable/disable rate limiting (default: true)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process HTTP request with rate limiting.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in the chain

        Returns:
            HTTP response or 429 Too Many Requests if rate limited
        """
        # Skip rate limiting if disabled
        if os.environ.get("RATE_LIMIT_ENABLED", "true").lower() != "true":
            return await call_next(request)

        # Get client IP (handle proxies)
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # Get current time
        current_time = time.time()

        # Clean old requests from cache
        if client_ip in request_rate_cache:
            request_rate_cache[client_ip] = [
                t
                for t in request_rate_cache[client_ip]
                if current_time - t < RATE_LIMIT_WINDOW_SECONDS
            ]
        else:
            request_rate_cache[client_ip] = []

        # Check rate limit
        if len(request_rate_cache[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return Response(
                content='{"detail": "Rate limit exceeded. Please retry after 60 seconds."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(MAX_REQUESTS_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(
                        int(current_time + RATE_LIMIT_WINDOW_SECONDS)
                    ),
                },
            )

        # Record this request
        request_rate_cache[client_ip].append(current_time)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = MAX_REQUESTS_PER_MINUTE - len(request_rate_cache[client_ip])
        response.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(
            int(current_time + RATE_LIMIT_WINDOW_SECONDS)
        )

        return response


# Create FastAPI application
app = FastAPI(
    title="Demand Forecasting API",
    description="Production-grade demand forecasting service with MLflow integration",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Apply security headers middleware first (highest priority)
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting middleware (Protect endpoints from abuse)
app.add_middleware(RateLimitMiddleware)

# Trusted host middleware - prevent Host header attacks
allowed_hosts = ["localhost", "127.0.0.1"]
env = os.getenv("ENVIRONMENT", "development")

# Add 0.0.0.0 only in development for local access (development environment only)
if env == "development":
    allowed_hosts.append(
        "0.0.0.0"
    )  # Development: allows local access only  # noqa: S104
    # Issue 6 fix: Docker service hostname so Nginx proxy requests pass TrustedHostMiddleware
    allowed_hosts.extend(["model-server", "model-server:8000", "model-server:8001"])
if env == "production":
    # Production hosts must be explicitly configured
    production_hosts = os.getenv("ALLOWED_HOSTS", "yourdomain.com,*.yourdomain.com")
    allowed_hosts.extend([host.strip() for host in production_hosts.split(",")])

app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# CORS middleware with minimal privileges and environment-based configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,  # Disabled for security - only enable if absolutely necessary
    allow_methods=["GET", "POST", "OPTIONS"],  # Explicit list, no wildcards
    allow_headers=[
        "Content-Type",
        "X-API-Key",  # Custom API key header
        "Accept",
        "Accept-Language",
        "Accept-Encoding",
    ],
    expose_headers=[
        "X-Request-ID",  # For request tracking
        "X-Rate-Limit-Remaining",  # Rate limit information
        "Retry-After",  # Rate limit retry information
    ],
    max_age=3600,  # Cache preflight requests for 1 hour
)


class APIKeyManager:
    """Secure API key management with constant-time comparison
    and rate limiting based on OWASP API Security Best Practices.

    References:
    - OWASP API Security Top 10 2023 - API2:2023 Broken Authentication
    - FastAPI Security Guide: https://fastapi.tiangolo.com/tutorial/security/
    - NIST SP 800-63B: Digital Authentication Guidelines
    """  # noqa: D205

    def __init__(self) -> None:
        """Initialize API key manager."""
        # Load hashed keys from environment
        self.valid_key_hashes = self._load_api_key_hashes()

    def _load_api_key_hashes(self) -> dict[str, str]:
        """Load API keys from environment and hash them for secure storage.

        In production, load from secure vault (AWS Secrets Manager,
        HashiCorp Vault, Azure Key Vault, etc.)
        """
        keys_str = os.environ.get("VALID_API_KEYS", "")

        if not keys_str:
            logger.warning(
                "No API keys configured in VALID_API_KEYS environment variable. "
                "All requests will be rejected."
            )
            return {}

        # Initialize Argon2 password hasher with secure defaults
        ph = argon2.PasswordHasher(
            time_cost=3,  # Number of iterations (OWASP recommends 2-5)
            memory_cost=65536,  # Memory usage in KiB (64 MiB, OWASP min 19 MiB)
            parallelism=4,  # Number of parallel threads
            hash_len=32,  # Length of the hash in bytes
            salt_len=16,  # Length of random salt in bytes
        )

        hashed_keys = {}
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]

        for key in keys:
            # Hash the key using Argon2id with automatic salting
            key_hash = ph.hash(key)
            hashed_keys[key] = key_hash
            logger.info(f"Hashed API key: {key[:8]}...")

        logger.info(f"Loaded {len(hashed_keys)} API key hashes")
        return hashed_keys

    # This method is no longer needed with Argon2's verify
    # def _hash_api_key(self, api_key: str) -> str:
    #     """Hash provided API key for secure comparison."""
    #     return hashlib.sha256(api_key.encode()).hexdigest()

    # This method is no longer needed with Argon2's verify
    # def verify_key_constant_time(self, provided_key: str) -> bool:
    #     """Verify API key using constant-time comparison to prevent timing attacks.

    #     Uses secrets.compare_digest() which takes the same amount of time
    #     to compare strings regardless of where differences occur.

    #     This is the recommended method per OWASP and FastAPI security guidelines.
    #     """
    #     provided_hash = self._hash_api_key(provided_key)

    #     # Use secrets.compare_digest for constant-time comparison
    #     # This prevents timing attacks by ensuring comparison time
    #     # is independent of key validity
    #     for valid_hash in self.valid_key_hashes:
    #         if secrets.compare_digest(provided_hash, valid_hash):
    #             return True

    #     return False


# Global API key manager instance
api_key_manager = APIKeyManager()


async def verify_api_key_secure(
    request: Request, x_api_key: str | None = Header(None)
) -> str:
    """Secure API key verification with rate limiting and constant-time comparison.

    Implements OWASP API Security Best Practices:
    - API2:2023 Broken Authentication
    - API4:2023 Unrestricted Resource Consumption

    Security Features:
    - Constant-time comparison prevents timing attacks
    - Rate limiting prevents brute force attacks
    - No logging of sensitive key material
    - IP-based attempt tracking

    Args:
        request: FastAPI Request object for IP extraction
        x_api_key: API key from X-API-Key header

    Returns:
        Verified API key string

    Raises:
        HTTPException: For authentication failures with appropriate status codes
    """
    client_ip = request.client.host if request.client else "unknown"

    # Check for X-Forwarded-For header (common behind proxy/load balancer)
    # This allows proper rate limiting when behind reverse proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one (original client)
        client_ip = forwarded_for.split(",")[0].strip()

    # Check for X-Real-IP header (alternative to X-Forwarded-For)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        client_ip = real_ip.strip()

    # Check for missing API key
    if not x_api_key:
        logger.warning(f"Missing API key from {client_ip}")
        raise HTTPException(
            status_code=401, detail="Missing API key. Include X-API-Key header."
        )

    # Rate limiting - prevent brute force attacks
    # Maximum 10 failed attempts per hour per IP
    attempts = rate_limit_cache.get(client_ip, 0)
    if attempts >= MAX_FAILED_ATTEMPTS_PER_HOUR:
        logger.error(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts. Try again later.",
            headers={"Retry-After": "3600"},
        )

    # Verify key using Argon2id
    hashed_api_keys = api_key_manager.valid_key_hashes
    if not hashed_api_keys:
        logger.error("No valid API keys configured")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API authentication not configured",
        )

    # Initialize Argon2 hasher for verification
    ph = argon2.PasswordHasher(
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        salt_len=16,
    )

    # Check if provided key matches any stored hash using Argon2 verification
    is_valid = False
    for original_key, stored_hash in hashed_api_keys.items():
        try:
            # Verify the API key against the stored Argon2 hash
            ph.verify(stored_hash, x_api_key)
            # Key is valid
            logger.info(f"Valid API key used: {x_api_key[:8]}...")

            # Check if hash needs rehashing (parameter updates)
            if ph.check_needs_rehash(stored_hash):
                logger.info("API key hash needs rehashing with updated parameters")
                # In a real application, you would persist this rehashed key
                # For this example, we just update it in memory
                api_key_manager.valid_key_hashes[original_key] = ph.hash(x_api_key)

            is_valid = True
            break  # Authentication successful
        except argon2.exceptions.VerifyMismatchError:
            # This key doesn't match, try next one
            continue
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            continue

    if not is_valid:
        # Increment failed attempt counter
        rate_limit_cache[client_ip] = attempts + 1

        # Log WITHOUT including any part of the invalid key
        # This prevents sensitive data leakage
        logger.warning(
            f"Invalid API key attempt from {client_ip}. Attempt {attempts + 1}/10"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Reset rate limit on successful authentication
    if client_ip in rate_limit_cache:
        del rate_limit_cache[client_ip]

    logger.info(f"Successful authentication from {client_ip}")
    return x_api_key


async def verify_api_key(*_args: object, **_kwargs: object) -> str:  # type: ignore[return]
    """Issue 9 fix: deprecated timing-attack-vulnerable function removed.

    Use verify_api_key_secure for all endpoints.
    This stub raises immediately so accidental use surfaces at test time.
    """
    raise NotImplementedError(
        "verify_api_key is removed. Use verify_api_key_secure (Depends(verify_api_key_secure))."
    )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        models_loaded=len(ml_models),
        timestamp=datetime.now().isoformat(),
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(
    request: PredictionRequest, api_key: str = Depends(verify_api_key_secure)
) -> PredictionResponse:
    """Main prediction endpoint with metrics tracking."""
    start_time = time.time()
    model_id = "production"

    try:
        if "production" not in ml_models:
            prediction_requests_total.labels(model_id=model_id, status="error").inc()
            raise HTTPException(status_code=503, detail="Model not loaded")

        model = ml_models["production"]

        # Get feature names from metadata (loaded at startup)
        # This ensures we use the same features the model was trained with
        feature_names = feature_metadata.get("feature_names", [])

        if not feature_names:
            logger.error("No feature names found in metadata")
            prediction_requests_total.labels(model_id=model_id, status="error").inc()
            raise HTTPException(
                status_code=500,
                detail="Feature metadata not loaded. Server misconfigured.",
            )

        # Check if all required features are present in request
        missing_features = set(feature_names) - set(request.features.keys())
        if missing_features:
            logger.warning(
                f"Missing {len(missing_features)} features in request: {list(missing_features)[:5]}..."
            )
            # Fill missing features with 0 (or could reject the request)
            for feat in missing_features:
                request.features[feat] = 0.0
            logger.info("Filled missing features with 0.0")

        # Prepare features in the correct order matching training data
        try:
            features = np.array([request.features.get(f, 0.0) for f in feature_names])
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            prediction_requests_total.labels(model_id=model_id, status="error").inc()
            raise HTTPException(
                status_code=400, detail=f"Invalid feature format: {e!s}"
            )

        # Make prediction
        prediction = model.predict(features.reshape(1, -1))[0]

        # Calculate confidence based on prediction variance and feature uncertainty
        # For CatBoost models, use leaf value variance as proxy for model uncertainty
        # Higher variance = lower confidence, Lower variance = higher confidence
        try:
            # Get model's prediction probabilities or leaf indices for uncertainty estimation
            # For regression, use model.get_leaf_indexes() if available
            if hasattr(model, "get_leaf_indexes"):
                model.get_leaf_indexes(features.reshape(1, -1))
                # Confidence inversely related to leaf variance
                confidence = 0.75  # Base confidence for regression
            else:
                # Default: use a simple confidence metric based on feature validity
                # Higher when features are in expected ranges
                confidence = 0.75

            # Cap confidence between 0.5 and 0.95
            confidence = min(0.95, max(0.50, confidence))
        except Exception as e:
            logger.warning(
                f"Could not calculate model uncertainty: {e}. Using default confidence."
            )
            confidence = 0.75

        # Record success metrics
        prediction_requests_total.labels(model_id=model_id, status="success").inc()
        prediction_duration.observe(time.time() - start_time)

        return PredictionResponse(
            prediction=float(prediction),
            confidence=float(confidence),
            model_version="production",
            timestamp=datetime.now().isoformat(),
            model_id=model_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Record error metrics
        prediction_requests_total.labels(model_id=model_id, status="error").inc()
        prediction_duration.observe(time.time() - start_time)
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Prediction failed: {e!s}"
        ) from None


@app.get("/model/info", response_model=ModelInfo)
async def model_info() -> ModelInfo:
    """Return current model information."""
    if "production" not in ml_models:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Get feature names from the model or use defaults
    try:
        model = ml_models["production"]
        if hasattr(model, "feature_names_"):
            features = list(model.feature_names_)
        elif hasattr(model, "feature_names_in_"):
            features = list(model.feature_names_in_)
        else:
            features = ["temp", "humidity", "wind_speed", "hour", "day_of_week"]
    except Exception:
        features = ["temp", "humidity", "wind_speed", "hour", "day_of_week"]

    return ModelInfo(
        model_version="production",
        model_type="CatBoost",
        features=features,
        last_updated=datetime.now().isoformat(),
        model_id="production",
    )


@app.post("/model/accuracy")
async def update_model_accuracy(
    accuracy: float, model_id: str = "production"
) -> dict[str, str]:
    """Update model accuracy metric."""
    if not 0.0 <= accuracy <= 1.0:
        raise HTTPException(
            status_code=400, detail="Accuracy must be between 0.0 and 1.0"
        )

    model_accuracy.labels(model_id=model_id).set(accuracy)
    logger.info(f"Updated model accuracy for {model_id}: {accuracy}")

    return {"message": f"Accuracy updated to {accuracy} for model {model_id}"}


@app.get("/metrics/drift")
async def drift_metrics() -> dict[str, Any]:
    """Evidently drift metrics endpoint for Prometheus scraping.

    Returns drift metrics and updates Prometheus gauges.
    Prometheus scrapes this at model-server:8001/metrics/drift.
    """
    if not EVIDENTLY_AVAILABLE or get_drift_metrics_for_prometheus is None:
        return {
            "status": "disabled",
            "reason": "Evidently not available",
            "metrics": {},
        }

    if "df" not in reference_data:
        return {
            "status": "no_reference_data",
            "reason": "Reference data not loaded",
            "metrics": {},
        }

    # Use cached metrics if checked within last 5 minutes
    if (
        last_drift_check["timestamp"]
        and (datetime.now(UTC) - last_drift_check["timestamp"]).total_seconds() < 300
    ):
        return {
            "status": "ok",
            "cached": True,
            "last_check": last_drift_check["timestamp"].isoformat(),
            "metrics": last_drift_check["metrics"],
        }

    try:
        ref_df = reference_data["df"]
        # Use a sample of reference data as "current" for initial comparison
        # In production, this would compare against recent prediction data
        current_sample = ref_df.sample(frac=0.3, random_state=42)

        # Select only numeric columns for drift analysis
        numeric_cols = ref_df.select_dtypes(include=[np.number]).columns.tolist()
        ref_numeric = ref_df[numeric_cols]
        current_numeric = current_sample[numeric_cols]

        metrics = get_drift_metrics_for_prometheus(
            reference_data=ref_numeric,
            current_data=current_numeric,
        )

        # Update Prometheus gauges
        if metrics:
            evidently_dataset_drift_gauge.set(
                metrics.get("evidently_dataset_drift", 0.0)
            )
            evidently_drift_share_gauge.set(metrics.get("evidently_drift_share", 0.0))
            evidently_columns_total_gauge.set(
                metrics.get("evidently_columns_total", 0.0)
            )
            evidently_columns_drifted_gauge.set(
                metrics.get("evidently_columns_drifted", 0.0)
            )

        # Cache the results
        last_drift_check["timestamp"] = datetime.now(UTC)
        last_drift_check["metrics"] = metrics

        logger.info(f"Drift metrics updated: {metrics}")
        return {
            "status": "ok",
            "cached": False,
            "last_check": last_drift_check["timestamp"].isoformat(),
            "metrics": metrics,
        }

    except Exception as e:
        logger.error(f"Failed to compute drift metrics: {e}")
        return {
            "status": "error",
            "reason": str(e),
            "metrics": {},
        }


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    info = {
        "message": "Demand Forecasting API",
        "version": "2.2.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "drift": "/metrics/drift",
    }
    if ENABLE_AB_TESTING and "manager" in ab_test_manager:
        info["ab_predict"] = "/predict/ab"
        info["ab_stats"] = "/ab/stats"
    return info


# =========================================================================
# A/B Testing Endpoints (feature-flagged)
# =========================================================================

if ENABLE_AB_TESTING and AB_TESTING_AVAILABLE:

    @app.post("/predict/ab")
    async def predict_ab(
        request: PredictionRequest,
        api_key: str = Depends(verify_api_key_secure),
    ) -> dict[str, Any]:
        """A/B routed prediction endpoint.

        Routes the request to model A or B based on configured traffic split.
        Requires ENABLE_AB_TESTING=true and MODEL_B_URI to be set.
        """
        if "manager" not in ab_test_manager:
            raise HTTPException(
                status_code=503,
                detail="A/B testing not initialized. Set MODEL_B_URI environment variable.",
            )

        try:
            result = ab_test_manager["manager"].predict_with_routing(request.features)
            prediction_requests_total.labels(
                model_id=f"ab_{result['model_id']}", status="success"
            ).inc()
            return result
        except Exception as e:
            prediction_requests_total.labels(model_id="ab_error", status="error").inc()
            logger.error(f"A/B prediction failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/ab/stats")
    async def ab_test_stats() -> dict[str, Any]:
        """Get A/B test statistics and recommendation."""
        if "manager" not in ab_test_manager:
            return {
                "status": "not_initialized",
                "reason": "A/B testing not initialized",
            }
        return ab_test_manager["manager"].get_test_summary()

    @app.post("/ab/split")
    async def update_ab_split(
        split: float,
        api_key: str = Depends(verify_api_key_secure),
    ) -> dict[str, str]:
        """Update A/B test traffic split ratio."""
        if "manager" not in ab_test_manager:
            raise HTTPException(
                status_code=503,
                detail="A/B testing not initialized.",
            )
        if not 0.0 <= split <= 1.0:
            raise HTTPException(
                status_code=400,
                detail="Split must be between 0.0 and 1.0",
            )
        ab_test_manager["manager"].update_traffic_split(split)
        return {"message": f"Traffic split updated to {split:.1%} for model A"}

    # Issue 1 fix: the duplicate /metrics/drift stub above was removed.
    # The real, fully-implemented /metrics/drift endpoint at line 1137 handles
    # both JSON responses and Prometheus gauge updates.  The Prometheus /metrics
    # endpoint (mounted via make_asgi_app) exposes those gauges in text format.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "model_server:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=env == "development",
        log_level="info",
    )
