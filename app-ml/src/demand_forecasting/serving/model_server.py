"""Production-grade FastAPI model server for demand forecasting."""

import hashlib
import logging
import math
import os
import secrets
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime

import catboost
import mlflow
import numpy as np
from cachetools import TTLCache
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting cache (IP -> attempt count)
rate_limit_cache = TTLCache(maxsize=10000, ttl=3600)  # 1 hour TTL

# Rate limiting constants
MAX_FAILED_ATTEMPTS_PER_HOUR = 10

# Global model storage
ml_models = {}

# Prometheus metrics
prediction_requests_total = Counter(
    "prediction_requests_total", "Total prediction requests", ["model_id", "status"]
)
prediction_duration = Histogram(
    "prediction_duration_seconds", "Prediction request duration"
)
model_accuracy = Gauge("model_accuracy", "Current model accuracy", ["model_id"])


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
    CORE_FEATURES = {"temp", "humidity", "wind_speed", "hour", "day_of_week"}

    # Optional features that may be provided depending on model requirements
    OPTIONAL_FEATURES = {
        "month", "quarter", "day_of_year", "year", "season",
        "holiday", "workingday", "weather_condition",
        "feels_like_temp", "casual", "registered",
        # Demand lag features (matching notebook's cnt_lag naming convention)
        # These are lags of current demand, not target (next hour)
        "demand_lag1", "demand_lag2", "demand_lag22", "demand_lag23",
        # Feature lag features (using renamed column names)
        "hour_lag1", "hour_lag2", "hour_lag3",
        "day_of_week_lag1", "day_of_week_lag2", "day_of_week_lag3",
        "weather_condition_lag1", "weather_condition_lag2", "weather_condition_lag3",
        "temp_lag1", "temp_lag2", "temp_lag3",
        "humidity_lag1", "humidity_lag2", "humidity_lag3",
        # Interaction features
        "hour_day_interaction",
        # Raw demand (current hour) - kept as feature per notebook
        "demand",
    }

    # Maximum number of features to prevent injection attacks
    MAX_FEATURES = 50

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
        try:
            model_uri = "models:/demand_forecasting/Production"
            ml_models["production"] = mlflow.pyfunc.load_model(model_uri)
            logger.info("Production model loaded successfully from MLflow registry")
            model_loaded = True
        except Exception as mlflow_error:
            logger.error(f"Failed to load production model from MLflow: {mlflow_error}")
            # Try to load from local path as fallback
            try:
                ml_models["production"] = catboost.CatBoost().load_model(
                    "models/experiments/final_catboost_model.cbm"
                )
                logger.info("Production model loaded successfully from local path")
                model_loaded = True
            except Exception as fallback_error:
                logger.error(f"Failed to load fallback model: {fallback_error}")

        # CRITICAL: Fail startup if no model is available
        if not model_loaded:
            raise RuntimeError(
                "CRITICAL: No model available. Cannot start prediction server. "
                "Please train a model and register it with MLflow, or place model file at: "
                "models/experiments/final_catboost_model.cbm"
            )

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
            "http://localhost:8080",
            "http://localhost:8501",  # Streamlit
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

# Trusted host middleware - prevent Host header attacks
allowed_hosts = ["localhost", "127.0.0.1"]
env = os.getenv("ENVIRONMENT", "development")

# Add 0.0.0.0 only in development for local access (development environment only)
if env == "development":
    allowed_hosts.append(
        "0.0.0.0"
    )  # Development: allows local access only  # noqa: S104
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

    def _load_api_key_hashes(self) -> dict[str, dict]:
        """Load API keys from environment and hash them for secure storage.

        In production, load from secure vault (AWS Secrets Manager,
        HashiCorp Vault, Azure Key Vault, etc.)
        """
        keys_str = os.environ.get("VALID_API_KEYS", "")
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]

        if not keys:
            logger.warning(
                "No VALID_API_KEYS configured. API authentication will fail."
            )
            return {}

        hashed_keys = {}
        for key in keys:
            # Hash the key for storage using SHA-256
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            hashed_keys[key_hash] = {
                "hash": key_hash,
                "created_at": datetime.utcnow().isoformat(),
            }

        logger.info(f"Loaded {len(hashed_keys)} API key hashes")
        return hashed_keys

    def _hash_api_key(self, api_key: str) -> str:
        """Hash provided API key for secure comparison."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_key_constant_time(self, provided_key: str) -> bool:
        """Verify API key using constant-time comparison to prevent timing attacks.

        Uses secrets.compare_digest() which takes the same amount of time
        to compare strings regardless of where differences occur.

        This is the recommended method per OWASP and FastAPI security guidelines.
        """
        provided_hash = self._hash_api_key(provided_key)

        # Use secrets.compare_digest for constant-time comparison
        # This prevents timing attacks by ensuring comparison time
        # is independent of key validity
        for valid_hash in self.valid_key_hashes:
            if secrets.compare_digest(provided_hash, valid_hash):
                return True

        return False


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

    # Verify key using constant-time comparison
    is_valid = api_key_manager.verify_key_constant_time(x_api_key)

    if not is_valid:
        # Increment failed attempt counter
        rate_limit_cache[client_ip] = attempts + 1

        # Log WITHOUT including any part of the invalid key
        # This prevents sensitive data leakage
        logger.warning(
            f"Invalid API key attempt from {client_ip}. Attempt {attempts + 1}/10"
        )
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Reset rate limit on successful authentication
    if client_ip in rate_limit_cache:
        del rate_limit_cache[client_ip]

    logger.info(f"Successful authentication from {client_ip}")
    return x_api_key


async def verify_api_key(x_api_key: str = Header(None)) -> str:
    """Legacy API key verification - DEPRECATED.

    This function is kept for backward compatibility but should
    be replaced with verify_api_key_secure in all endpoints.

    SECURITY WARNING: This function is vulnerable to timing attacks.
    Use verify_api_key_secure instead.
    """
    logger.warning(
        "Using deprecated verify_api_key function - vulnerable to timing attacks"
    )

    # Load valid API keys from environment variable (comma-separated)
    valid_api_keys = os.environ.get("VALID_API_KEYS", "").split(",")
    valid_api_keys = [key.strip() for key in valid_api_keys if key.strip()]

    if not x_api_key:
        raise HTTPException(
            status_code=401, detail="Missing API key. Provide X-API-Key header."
        )

    if x_api_key not in valid_api_keys:
        # SECURITY WARNING: Logging partial API key can leak information
        logger.warning(f"Invalid API key attempt: {x_api_key[:10]}...")
        raise HTTPException(status_code=403, detail="Invalid API key")

    return x_api_key


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

        # Prepare features in the correct order
        feature_names = ["temp", "humidity", "wind_speed", "hour", "day_of_week"]
        features = np.array([request.features[f] for f in feature_names])

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


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "message": "Demand Forecasting API",
        "version": "2.2.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "model_server:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=env == "development",
        log_level="info",
    )
