#!/bin/bash

# Install MLflow and dependencies
pip install mlflow psycopg2-binary

# Set environment variables for MLflow
export MLFLOW_BACKEND_STORE_URI=postgresql://airflow:airflow@postgres:5432/mlflow
export MLFLOW_DEFAULT_ARTIFACT_ROOT=s3://mlflow-artifacts/

# Start MLflow server with correct configuration
mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --backend-store-uri postgresql://airflow:airflow@postgres:5432/mlflow \
    --default-artifact-root s3://mlflow-artifacts/ \
    --allowed-hosts '*' \
    --cors-allowed-origins '*' \
    --serve-artifacts
