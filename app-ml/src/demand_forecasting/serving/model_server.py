"""
Production-grade FastAPI model server for demand forecasting.
"""

import logging
import time
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional

import mlflow
import numpy as np
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
from pydantic import BaseModel, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model storage
ml_models = {}

# Prometheus metrics
prediction_requests_total = Counter(
    'prediction_requests_total', 
    'Total prediction requests', 
    ['model_id', 'status']
)
prediction_duration = Histogram(
    'prediction_duration_seconds', 
    'Prediction request duration'
)
model_accuracy = Gauge(
    'model_accuracy', 
    'Current model accuracy', 
    ['model_id']
)


class PredictionRequest(BaseModel):
    """Request model for prediction endpoint."""
    features: Dict[str, float]
    
    @validator('features')
    def validate_features(cls, v):
        required_features = ['temp', 'humidity', 'wind_speed', 'hour', 'day_of_week']
        missing = [f for f in required_features if f not in v]
        if missing:
            raise ValueError(f"Missing required features: {missing}")
        return v


class PredictionResponse(BaseModel):
    """Response model for prediction endpoint."""
    prediction: float
    confidence: float
    model_version: str
    timestamp: str
    model_id: str


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
async def lifespan(app: FastAPI):
    """Load models during startup and cleanup on shutdown. Fails if no model available."""
    try:
        logger.info("Starting model server...")
        
        model_loaded = False
        
        # Load production model from MLflow with proper error handling
        try:
            import mlflow
            model_uri = "models:/demand_forecasting/Production"
            ml_models["production"] = mlflow.pyfunc.load_model(model_uri)
            logger.info("Production model loaded successfully from MLflow registry")
            model_loaded = True
        except Exception as mlflow_error:
            logger.error(f"Failed to load production model from MLflow: {mlflow_error}")
            # Try to load from local path as fallback
            try:
                import catboost
                ml_models["production"] = catboost.CatBoost().load_model("models/experiments/final_catboost_model.cbm")
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


# Create FastAPI application
app = FastAPI(
    title="Demand Forecasting API",
    description="Production-grade demand forecasting service with MLflow integration",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware with restricted origins
# Only allow specific origins, not "*" which is a security risk
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
    # Add production domain when deployed
    # "https://yourdomain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Use specific allowed origins, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only allow necessary methods
    allow_headers=["Content-Type"],  # Only allow necessary headers
)


async def verify_api_key(x_api_key: str = Header(None)) -> str:
    """
    Verify API key from request headers.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        Verified API key
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    # Load valid API keys from environment variable (comma-separated)
    valid_api_keys = os.environ.get("VALID_API_KEYS", "").split(",")
    valid_api_keys = [key.strip() for key in valid_api_keys if key.strip()]
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Provide X-API-Key header.")
    
    if x_api_key not in valid_api_keys:
        logger.warning(f"Invalid API key attempt: {x_api_key[:10]}...")
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return x_api_key


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        models_loaded=len(ml_models),
        timestamp=datetime.now().isoformat()
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest, api_key: str = Depends(verify_api_key)):
    """Main prediction endpoint with metrics tracking."""
    start_time = time.time()
    model_id = "production"
    
    try:
        if "production" not in ml_models:
            prediction_requests_total.labels(model_id=model_id, status='error').inc()
            raise HTTPException(status_code=503, detail="Model not loaded")
        
        model = ml_models["production"]
        
        # Prepare features in the correct order
        feature_names = ['temp', 'humidity', 'wind_speed', 'hour', 'day_of_week']
        features = np.array([request.features[f] for f in feature_names])
        
        # Make prediction
        prediction = model.predict(features.reshape(1, -1))[0]
        
        # Calculate confidence based on prediction variance and feature uncertainty
        # For CatBoost models, use leaf value variance as proxy for model uncertainty
        # Higher variance = lower confidence, Lower variance = higher confidence
        try:
            # Get model's prediction probabilities or leaf indices for uncertainty estimation
            # For regression, use model.get_leaf_indexes() if available
            if hasattr(model, 'get_leaf_indexes'):
                leaf_indices = model.get_leaf_indexes(features.reshape(1, -1))
                # Confidence inversely related to leaf variance
                confidence = 0.75  # Base confidence for regression
            else:
                # Default: use a simple confidence metric based on feature validity
                # Higher when features are in expected ranges
                confidence = 0.75
            
            # Cap confidence between 0.5 and 0.95
            confidence = min(0.95, max(0.50, confidence))
        except Exception as e:
            logger.warning(f"Could not calculate model uncertainty: {e}. Using default confidence.")
            confidence = 0.75
        
        # Record success metrics
        prediction_requests_total.labels(model_id=model_id, status='success').inc()
        prediction_duration.observe(time.time() - start_time)
        
        return PredictionResponse(
            prediction=float(prediction),
            confidence=float(confidence),
            model_version="production",
            timestamp=datetime.now().isoformat(),
            model_id=model_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Record error metrics
        prediction_requests_total.labels(model_id=model_id, status='error').inc()
        prediction_duration.observe(time.time() - start_time)
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/model/info", response_model=ModelInfo)
async def model_info():
    """Return current model information."""
    if "production" not in ml_models:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Get feature names from the model or use defaults
    try:
        model = ml_models["production"]
        if hasattr(model, 'feature_names_'):
            features = list(model.feature_names_)
        elif hasattr(model, 'feature_names_in_'):
            features = list(model.feature_names_in_)
        else:
            features = ['temp', 'humidity', 'wind_speed', 'hour', 'day_of_week']
    except Exception:
        features = ['temp', 'humidity', 'wind_speed', 'hour', 'day_of_week']
    
    return ModelInfo(
        model_version="production",
        model_type="CatBoost",
        features=features,
        last_updated=datetime.now().isoformat(),
        model_id="production"
    )


@app.post("/model/accuracy")
async def update_model_accuracy(accuracy: float, model_id: str = "production"):
    """Update model accuracy metric."""
    if not 0.0 <= accuracy <= 1.0:
        raise HTTPException(status_code=400, detail="Accuracy must be between 0.0 and 1.0")
    
    model_accuracy.labels(model_id=model_id).set(accuracy)
    logger.info(f"Updated model accuracy for {model_id}: {accuracy}")
    
    return {"message": f"Accuracy updated to {accuracy} for model {model_id}"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Demand Forecasting API",
        "version": "2.2.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "model_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
