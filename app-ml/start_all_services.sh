#!/bin/bash

echo "Starting all services for Demand Forecasting MLOps System..."
echo "============================================================"

# Navigate to app-ml directory
cd "$(dirname "$0")"

echo ""
echo "Step 1: Starting core infrastructure (postgres, redis, minio)..."
docker-compose up -d postgres redis minio

echo ""
echo "Step 2: Waiting for core services to be healthy..."
sleep 10

echo ""
echo "Step 3: Creating MinIO buckets..."
docker-compose up createbuckets

echo ""
echo "Step 4: Starting MLflow..."
docker-compose up -d mlflow

echo ""
echo "Step 5: Waiting for MLflow to be ready..."
sleep 15

echo ""
echo "Step 6: Starting Airflow services..."
docker-compose up -d airflow-init
sleep 10
docker-compose up -d airflow-webserver airflow-scheduler airflow-triggerer airflow-worker

echo ""
echo "Step 7: Waiting for Airflow to be ready..."
sleep 20

echo ""
echo "Step 8: Starting Model Server..."
docker-compose up -d model-server

echo ""
echo "Step 9: Waiting for Model Server to be healthy..."
sleep 15

echo ""
echo "Step 10: Starting Nginx..."
docker-compose up -d nginx

echo ""
echo "Step 11: Starting Monitoring (Prometheus & Grafana)..."
docker-compose up -d prometheus grafana

echo ""
echo "============================================================"
echo "All services started! Checking status..."
echo ""
docker-compose ps

echo ""
echo "============================================================"
echo "Service URLs:"
echo "  - Airflow UI: http://localhost:8081 (Cole/admin)"
echo "  - MLflow UI: http://localhost:5000"
echo "  - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo "  - Model Server: http://localhost:8000"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo "  - Nginx: http://localhost:80"
echo "============================================================"
