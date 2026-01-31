# Docker Compose Guide

## Overview

This document explains the different Docker Compose files available and when to use each one.

## 🎯 **Canonical Docker Compose File**

**RECOMMENDED:** `docker-compose.yml` (the unified stack)

**Current Status:** ✅ The unified configuration has been renamed to `docker-compose.yml` and is now the single canonical entrypoint.

**Why this change:** To simplify deployment and eliminate confusion about which compose file to use. The unified file contains the complete production-ready stack with all services.

## Docker Compose Files

### 1. `docker-compose.yml` (Unified Stack) ⭐ **RECOMMENDED**
**Purpose**: Complete ML pipeline with all services
**Services**: Airflow (full), PostgreSQL (multi-DB), Redis, MinIO, MLflow
**Use Case**: Production deployment and complete development environment

### 2. `docker-compose-enhanced.yml` (MLflow Stack)  
**Purpose**: MLflow experiment tracking with storage services
**Services**: PostgreSQL, Redis, MinIO, MLflow tracking server
**Use Case**: MLflow experiment tracking without Airflow orchestration

### 3. `docker-compose-unified.yml` (Complete Stack) ⭐ **RECOMMENDED**
**Purpose**: Complete ML pipeline with all services
**Services**: Airflow (full), PostgreSQL (multi-DB), Redis, MinIO, MLflow
**Use Case**: Production deployment and complete development environment

## Quick Start

### For Production/Complete Setup (Recommended)
```bash
# Copy environment template and configure
cp .env.example .env
# Edit .env with your real credentials and secrets

# Start the complete stack
docker-compose -f docker-compose-unified.yml up -d

# Access services:
# - Airflow: http://localhost:8080
# - MLflow: http://localhost:5000
# - MinIO Console: http://localhost:9001
```

### For Airflow-Only Development
```bash
# Start only Airflow stack
docker-compose -f docker-compose.yaml up -d

# Access Airflow: http://localhost:8080
```

### For MLflow-Only Experimentation
```bash
# Start MLflow with storage services
docker-compose -f docker-compose-enhanced.yml up -d

# Access MLflow: http://localhost:5000
# Access MinIO Console: http://localhost:9001
```

## Environment Configuration

All compose files require a `.env` file with the following key variables:

### Required Security Variables
```bash
# Generate these with proper tools (see .env.example)
AIRFLOW__CORE__FERNET_KEY=your_generated_fernet_key
AIRFLOW__WEBSERVER__SECRET_KEY=your_generated_secret_key
MINIO_ROOT_USER=your_minio_user
MINIO_ROOT_PASSWORD=your_minio_password
```

### Optional Configuration
```bash
# Email alerts (comma-separated)
AIRFLOW_ALERT_EMAIL=admin@company.com,dev-team@company.com

# MLflow/Optuna (for enhanced features)
MLFLOW_TRACKING_URI=http://mlflow:5000
OPTUNA_STORAGE_URL=postgresql://airflow:airflow@postgres:5432/optuna
```

## Service Endpoints

| Service | Port | Description |
|---------|------|-------------|
| Airflow Webserver | 8080 | DAG management and monitoring |
| MLflow Tracking | 5000 | Experiment tracking and model registry |
| MinIO API | 9000 | S3-compatible object storage |
| MinIO Console | 9001 | Web-based MinIO management |
| PostgreSQL | 5432 | Metadata and persistence |
| Redis | 6379 | Celery message broker |

## Production Considerations

### Security
- Never commit the actual `.env` file to version control
- Use strong, unique Fernet keys and secrets
- Change default MinIO credentials in production
- Configure proper network access controls

### Performance
- The unified stack includes resource limits for optimal performance
- PostgreSQL is configured with multiple databases (airflow, mlflow, optuna)
- Connection pooling is configured per service

### Monitoring
- All services include health checks
- Airflow logs are configured to remote MinIO storage
- Consider adding external monitoring (Prometheus/Grafana) for production

## Troubleshooting

### Common Issues
1. **Permission denied on .env**: Ensure proper file permissions
2. **Service startup failures**: Check environment variables in .env
3. **MinIO connection issues**: Verify endpoint and credentials
4. **Airflow Fernet key errors**: Regenerate key with proper tool

### Health Checks
```bash
# Check service status
docker-compose -f docker-compose-unified.yml ps

# View logs
docker-compose -f docker-compose-unified.yml logs -f [service-name]

# Restart specific service
docker-compose -f docker-compose-unified.yml restart [service-name]
```

## Migration Guide

### Moving from docker-compose.yaml to Unified
1. Stop existing services: `docker-compose down`
2. Update .env with any missing variables
3. Start unified stack: `docker-compose -f docker-compose-unified.yml up -d`
4. Verify all services are healthy

### Data Persistence
- PostgreSQL data persists in named volumes
- MinIO data persists in named volumes  
- No data migration required between compose files

---

**Recommendation**: Use `docker-compose-unified.yml` for all new deployments to ensure access to all features and avoid configuration confusion.
