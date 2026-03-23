#!/bin/bash
# =============================================================================
# MLflow Server Entrypoint
# =============================================================================
# Required environment variables:
#   - POSTGRES_USER: PostgreSQL username
#   - POSTGRES_PASSWORD: PostgreSQL password
#   - POSTGRES_HOST: PostgreSQL host (default: postgres)
#   - MLFLOW_S3_ENDPOINT_URL: MinIO/S3 endpoint URL (required for MinIO)
#   - AWS_ACCESS_KEY_ID: S3 access key
#   - AWS_SECRET_ACCESS_KEY: S3 secret key
# =============================================================================

set -e

# Install MLflow and dependencies
pip install mlflow psycopg2-binary boto3

# Validate required environment variables
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "ERROR: POSTGRES_PASSWORD environment variable is not set"
    exit 1
fi

# Set defaults
POSTGRES_USER=${POSTGRES_USER:-airflow}
POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
MLFLOW_DB=${MLFLOW_DB:-mlflow}

# Construct database URI
DB_URI="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${MLFLOW_DB}"

# Set environment variables for MLflow
export MLFLOW_BACKEND_STORE_URI="${DB_URI}"
export MLFLOW_DEFAULT_ARTIFACT_ROOT=s3://mlflow-artifacts/

# CRITICAL: Set S3 endpoint URL for MinIO compatibility
# Without this, MLflow will try to use AWS S3 instead of local MinIO
export MLFLOW_S3_ENDPOINT_URL=${MLFLOW_S3_ENDPOINT_URL:-http://minio:9000}

echo "Starting MLflow server..."
echo "  Backend Store: ${POSTGRES_HOST}:${POSTGRES_PORT}/${MLFLOW_DB}"
echo "  S3 Endpoint: ${MLFLOW_S3_ENDPOINT_URL}"
echo "  Artifact Root: ${MLFLOW_DEFAULT_ARTIFACT_ROOT}"

# Start MLflow server with correct configuration
mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --backend-store-uri "${DB_URI}" \
    --default-artifact-root s3://mlflow-artifacts/ \
    --allowed-hosts '*' \
    --serve-artifacts
