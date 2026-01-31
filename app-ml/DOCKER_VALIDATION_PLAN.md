# DOCKER VALIDATION TEST PLAN

## Overview
This document outlines the Docker Compose validation strategy for the fixed Demand Forecasting ML system.

## Docker Stack Components (15 services)
- PostgreSQL (metadata store)
- Redis (caching)
- MinIO (S3-compatible object storage)
- Apache Airflow (orchestration)
- MLflow (experiment tracking)
- Prometheus (monitoring)
- Grafana (dashboards)
- FastAPI (prediction serving)
- Supporting services

## Phase 1: Docker Image Build and Stack Startup

### Validation Points:
1. All Docker images build successfully
2. All services start without errors
3. Health checks pass for critical services
4. Network connectivity between services verified
5. Shared volumes mounted correctly

### Commands:
```bash
cd deployment
docker-compose build --no-cache
docker-compose up -d
docker-compose ps
```

## Phase 2: Service Health Verification

### Critical Service Checks:
- PostgreSQL: Connection test, schema verification
- Redis: Ping test, key-value operations
- MinIO: Bucket creation, file upload and download
- Airflow: DAG parsing, scheduler readiness
- MLflow: Server health, database connectivity
- FastAPI: Health endpoint response

## Phase 3: Pipeline Execution Tests

### Test 3.1: Data Processing Pipeline
- Load raw bike data
- Validate preprocessing output
- Check intermediate data quality
- Verify schema consistency

### Test 3.2: Feature Engineering Pipeline
- Extract temporal features
- Create feature interactions
- Validate lag features
- Ensure no NaN leakage

### Test 3.3: Demand Modeling Pipeline
- Run hyperparameter optimization using Optuna
- Train CatBoost model
- Train Random Forest model
- Compare model performance
- Select and train final model

### Test 3.4: Explainability Pipeline
- Generate SHAP explanations
- Calculate feature importance
- Log artifacts to MLflow
- Generate data quality report

### Test 3.5: Full Pipeline Integration
- Execute all 4 pipelines sequentially
- Verify data flow between stages
- Validate final artifacts
- Check MLflow run tracking

## Phase 4: Data and Artifact Validation

### Data Quality Checks:
- Row counts at each stage
- No null values in critical columns
- Correct data types (numerical, categorical)
- Feature ranges within expected bounds
- Temporal continuity for time-series

### Artifact Validation:
- Model serialization and deserialization
- SHAP values correctness
- Feature importance ranking
- Report generation
- MLflow artifact logging

## Phase 5: API and Serving Tests

### FastAPI Endpoints:
- POST /predict - Single prediction
- POST /batch-predict - Batch predictions
- GET /health - Service health
- GET /metrics - Performance metrics
- GET /model-info - Model metadata

## Phase 6: Monitoring and Logging

### Prometheus Metrics:
- Pipeline execution time
- Model accuracy metrics
- API request latency
- Service uptime
- Resource utilization

### Logs Verification:
- No ERROR level logs
- All INFO logs present
- Debug traces available
- Error stack traces captured

## Success Criteria

All tests must pass:
- All services healthy
- All pipelines execute without errors
- Data flows correctly through all stages
- Models train successfully
- Artifacts stored in MinIO and MLflow
- API responds to requests
- Monitoring metrics collected
- No critical errors in logs

Once all criteria met: APPROVED FOR PRODUCTION DEPLOYMENT

## Estimated Timeline
- Phase 1: 5-10 minutes
- Phase 2: 5-10 minutes
- Phase 3: 30-45 minutes
- Phase 4: 10-15 minutes
- Phase 5: 10-15 minutes
- Phase 6: 5-10 minutes

Total: approximately 90 minutes for complete Docker validation
