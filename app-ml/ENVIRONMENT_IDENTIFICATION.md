# ENVIRONMENT SETUP ANALYSIS
## Demand Forecasting ML System

**Analysis Date:** January 24, 2026  
**Status:** Two Complete Runtime Environments Identified

---

## ENVIRONMENT #1: LOCAL MICROMAMBA (PRIMARY DEVELOPMENT)

### Location
```
D:\micromamba\envs\demand-forecasting
```

### Runtime Details
| Property | Value |
|----------|-------|
| **Manager** | Micromamba (conda-based) |
| **Python Version** | 3.11.14 |
| **Total Packages** | 439 packages |
| **Package Source** | conda-forge, defaults channels |
| **Environment Type** | Development/Local Testing |

### Installed Components (Verified)
✅ **Orchestration:**
- Apache Airflow 2.10.4 ecosystem
- Airflow providers (Amazon, Celery, Docker, FAB, SQL, etc.)
- Celery 5.x

✅ **ML Framework:**
- Kedro 0.19.14
- Kedro-datasets 7.0.0
- Kedro-telemetry 0.7.0

✅ **ML Libraries:**
- CatBoost 1.2.8+
- XGBoost 2.0.0+
- LightGBM 4.0.0+
- Scikit-learn 1.5.0+
- Optuna 4.3.0+
- SHAP (for explainability)

✅ **Data Processing:**
- Pandas 2.2.0+
- NumPy 2.0.0+
- PyArrow 20.0.0+
- Pandera (schema validation)
- Great Expectations (data quality)

✅ **API & Web:**
- FastAPI 0.104.1+
- Uvicorn 0.24.0+
- Pydantic 2.5.0+

✅ **Monitoring & Tracking:**
- MLflow 3.8.1+
- Prometheus-client 0.19.0+

✅ **Utilities:**
- Pre-commit hooks 5.0.0+
- OmegaConf 2.3.0+ (for config management)
- Requests 2.32.5+
- Click 8.1.8+

### How It's Used Locally
```bash
# Activate environment
micromamba activate demand-forecasting

# Run Kedro pipeline
kedro run

# Run tests
pytest tests/ -v

# Run specific pipeline
kedro run --pipeline=demand_modeling

# Run FastAPI server locally
python src/demand_forecasting/serving/model_server.py
```

### Configuration Files
- **Requirements:** 
  - `requirements.txt` - All dependencies
  - `requirements.core.txt` - Core packages
  - `requirements.framework.txt` - Kedro framework
  - `requirements.ml.txt` - ML libraries
  - `requirements.airflow.txt` - Airflow-specific
  - `requirements-security.txt` - Security tools

- **Project Config:**
  - `.env` - Local environment variables
  - `.env.example` - Template for .env
  - `pyproject.toml` - Project metadata

### Advantages
✅ Local development/testing  
✅ No containerization overhead  
✅ Fast iteration  
✅ Full environment control  
✅ Debugging-friendly  

### Limitations
❌ Different from production Docker  
❌ OS-specific issues possible  
❌ Manual dependency management  
❌ Python version must match  

---

## ENVIRONMENT #2: DOCKER COMPOSE (PRODUCTION/CI-CD)

### Architecture
Multi-container orchestration with 12+ services

### Docker Setup Files
| File | Purpose |
|------|---------|
| `Dockerfile` | Main Airflow service image |
| `Dockerfile.model-server.ultra-optimized` | FastAPI model server |
| `docker-compose.yml` | Service orchestration (14,925 lines) |
| `.dockerignore` | Exclude files from build |
| `mlflow-entrypoint.sh` | MLflow startup script |
| `start_all_services.sh` | Bash startup automation |
| `start_all_services.ps1` | PowerShell startup automation |

### Container Services

#### **Infrastructure (Shared)**

1. **PostgreSQL 15-Alpine**
   - Port: 5432
   - Data: `postgres_data` volume
   - Databases: airflow, mlflow, optuna
   - Credentials: airflow/airflow

2. **Redis 7-Alpine**
   - Port: 6379
   - Data: `redis_data` volume
   - Password: redis123
   - Use: Celery broker + caching

3. **MinIO (S3-Compatible)**
   - Ports: 9000 (API), 9001 (Console)
   - Data: `minio_data` volume
   - Credentials: minioadmin/minioadmin
   - Buckets: demand-forecasting, mlflow-artifacts, airflow-logs

#### **MLOps Services**

4. **MLflow Tracking Server**
   - Image: `python:3.11-slim`
   - Port: 5000
   - Database: PostgreSQL mlflow schema
   - Artifact Storage: MinIO S3
   - Data: `mlflow_data` volume

#### **Airflow Ecosystem**

5. **Airflow Webserver**
   - Image: Built from `Dockerfile`
   - Port: 8081 (maps to 8080 internally)
   - Executor: LocalExecutor
   - Database: PostgreSQL airflow schema

6. **Airflow Scheduler**
   - Image: Built from `Dockerfile`
   - Purpose: DAG scheduling
   - Database: PostgreSQL airflow schema
   - Message Queue: Redis

7. **Airflow Worker (Celery)**
   - Image: Built from `Dockerfile`
   - Purpose: Task execution
   - Broker: Redis
   - Result Backend: Redis

8. **Airflow Triggerer**
   - Image: Built from `Dockerfile`
   - Purpose: Async trigger handling
   - Database: PostgreSQL

9. **Airflow Init**
   - Purpose: One-time initialization
   - Creates admin user (Cole/admin)
   - Migrates database

#### **Model Serving**

10. **FastAPI Model Server**
    - Image: Built from `Dockerfile.model-server.ultra-optimized`
    - Ports: 8000 (API), 8001 (Metrics)
    - Resources: 1.0 CPU limit, 2GB RAM limit
    - Volumes: models/, logs/, data/
    - Healthcheck: `/health` endpoint

#### **Testing**

11. **Test Runner** (profile: testing)
    - Image: `Dockerfile.model-server.ultra-optimized`
    - Purpose: CI/CD testing
    - Command: pytest with coverage
    - Volumes: tests/, src/, test_reports/

#### **Monitoring**

12. **NGINX Load Balancer**
    - Image: `nginx:alpine`
    - Ports: 80, 8080
    - Config: `./nginx/nginx.conf`
    - Logs: `nginx_logs` volume

13. **Prometheus**
    - Image: `prom/prometheus:latest`
    - Port: 9090
    - Config: `./prometheus/prometheus.yml`
    - Data: `prometheus_data` volume (15d retention)

14. **Grafana**
    - Image: `grafana/grafana:latest`
    - Port: 3000
    - Credentials: admin/admin
    - Provisioning: `./grafana/provisioning`
    - Dashboards: `./grafana/dashboards`

#### **Utilities**

15. **MinIO Bucket Creator**
    - Image: `minio/mc:latest`
    - Purpose: Initialize S3 buckets
    - One-time execution

### Docker Network
```yaml
Network: demand-forecasting-network (bridge driver)
All services connected for internal communication
```

### Docker Volumes
```yaml
postgres_data:      # PostgreSQL persistent storage
redis_data:         # Redis persistence
minio_data:         # MinIO object storage
mlflow_data:        # MLflow tracking data
nginx_logs:         # NGINX request logs
prometheus_data:    # Prometheus time-series data
grafana_data:       # Grafana configuration & dashboards
```

### Environment Variables (Docker)
```yaml
# Required (from .env file):
MINIO_ROOT_USER: (set in .env)
MINIO_ROOT_PASSWORD: (set in .env)
AIRFLOW__CORE__FERNET_KEY: (set in .env)
AIRFLOW__WEBSERVER__SECRET_KEY: (set in .env)
REDIS_PASSWORD: redis123 (hardcoded)

# Airflow Specific:
AIRFLOW__CORE__EXECUTOR: LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
AIRFLOW__CELERY__BROKER_URL: redis://redis:6379/0
AIRFLOW__CELERY__RESULT_BACKEND: redis://redis:6379/0
AIRFLOW__LOGGING__REMOTE_LOGGING: true
AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER: s3://airflow-logs

# MLflow:
DATABASE_URL: postgresql://airflow:airflow@postgres:5432/mlflow
MLFLOW_S3_ENDPOINT_URL: http://minio:9000
AWS_ACCESS_KEY_ID: minioadmin
AWS_SECRET_ACCESS_KEY: minioadmin

# Model Server:
MODEL_SERVER_HOST: 0.0.0.0
MODEL_SERVER_PORT: 8000
METRICS_PORT: 8001
MLFLOW_TRACKING_URI: http://mlflow:5000
```

### How It's Used (Docker)

**Start All Services:**
```bash
# Using docker-compose
docker-compose up -d

# Or using the automation script
./start_all_services.sh  # Linux/Mac
.\start_all_services.ps1  # Windows PowerShell
```

**View Services:**
```bash
docker-compose ps
```

**Access Services:**
```
Airflow UI: http://localhost:8081 (Cole/admin)
MLflow UI: http://localhost:5000
MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
Grafana: http://localhost:3000 (admin/admin)
Prometheus: http://localhost:9090
FastAPI Docs: http://localhost:8000/docs
Model Metrics: http://localhost:8001/metrics
NGINX: http://localhost or http://localhost:8080
```

**Run Tests in Docker:**
```bash
docker-compose --profile testing up test-runner
```

### Advantages
✅ Production-like environment  
✅ Consistent across machines  
✅ Full microservices architecture  
✅ Complete observability stack  
✅ CI/CD ready  
✅ Scalable to Kubernetes  

### Limitations
❌ Resource-intensive locally  
❌ Container startup overhead  
❌ Debugging more complex  
❌ Requires Docker/Docker Compose  

---

## COMPARISON MATRIX

| Aspect | Micromamba Local | Docker Compose |
|--------|------------------|-----------------|
| **Primary Use** | Development/Testing | Production/CI-CD |
| **Python Version** | 3.11.14 | 3.11 (in base images) |
| **Setup Time** | ~5-10 min | ~2-5 min (first run) |
| **Resource Usage** | Light | Heavy (all containers) |
| **Debugging** | Easy | Moderate |
| **Isolation** | No | Yes (containers) |
| **Reproducibility** | Medium | High |
| **Services** | Local Python only | 15 services |
| **Database** | Must install separately | Included (PostgreSQL) |
| **Message Queue** | Must install separately | Included (Redis) |
| **Monitoring** | Manual setup | Included (Prometheus/Grafana) |
| **S3 Storage** | Must use remote | Included (MinIO) |
| **MLflow** | Can run locally | Full containerized |
| **Scale** | Single machine | Multi-container |

---

## EXECUTION PATHS

### Path 1: Development Loop (Micromamba)
```
micromamba activate demand-forecasting
  ↓
kedro run (or specific pipeline)
  ↓
Tests pass ✅
  ↓
Changes committed
  ↓
Ready for Docker deployment
```

### Path 2: Production Deployment (Docker)
```
docker-compose up -d
  ↓
All services start (healthchecks verify)
  ↓
Airflow scheduler runs DAGs automatically
  ↓
Model server accepts predictions
  ↓
Monitoring collects metrics
  ↓
Grafana visualizes dashboards
```

### Path 3: CI/CD Testing (Docker)
```
docker-compose --profile testing up test-runner
  ↓
Tests execute with coverage
  ↓
Reports generated
  ↓
Coverage checked
  ↓
Pass/Fail decision
```

---

## KEY CONFIGURATION FILES

### Micromamba Setup
- `.env` - Environment variables (local)
- `.env.example` - Template
- `pyproject.toml` - Project metadata
- `requirements*.txt` - All dependencies

### Docker Setup
- `docker-compose.yml` - Full orchestration
- `Dockerfile` - Airflow image
- `Dockerfile.model-server.ultra-optimized` - Model server
- `.env` - Docker environment (required)
- `.dockerignore` - Build exclusions
- `mlflow-entrypoint.sh` - MLflow startup

### Service Configuration
- `conf/base/catalog.yml` - Data catalog
- `conf/base/parameters.yml` - ML parameters
- `conf/base/credentials.yml` - S3 credentials
- `nginx/nginx.conf` - NGINX routing
- `prometheus/prometheus.yml` - Metrics config
- `grafana/provisioning/` - Dashboard setup

---

## RECOMMENDATION FOR YOUR WORKFLOW

**Development:** Use **Micromamba** locally
- Faster iteration
- Easier debugging
- Lower resource usage

**Production/Testing:** Use **Docker Compose**
- Full integration
- Reproducible
- Automated monitoring

**Hybrid Approach:**
1. Develop with Micromamba
2. Test locally with Docker (validate changes)
3. Deploy to production with Docker

---

## SUMMARY

| Environment | Type | Python | Services | Use Case |
|-------------|------|--------|----------|----------|
| **Micromamba** | Local Dev | 3.11.14 | Python only | Development |
| **Docker** | Full Stack | 3.11 | 15+ containers | Production/CI-CD |

**Total Runtime Setup:** Two complete, independent environments  
**Primary Development:** Micromamba (D:\micromamba\envs\demand-forecasting)  
**Production:** Docker Compose (docker-compose.yml orchestration)
