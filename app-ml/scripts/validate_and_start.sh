#!/bin/bash
# =============================================================================
# VALIDATION AND STARTUP SCRIPT
# =============================================================================
# This script validates the environment and starts all services safely
# =============================================================================

set -e

echo "=========================================="
echo "Demand Forecasting ML System - Startup"
echo "=========================================="
echo ""

# Change to app-ml directory
cd "$(dirname "$0")/.."

# Step 1: Validate .env file exists
echo "Step 1: Validating environment configuration..."
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo "Please create .env file from .env.template"
    exit 1
fi
echo "✅ .env file found"

# Step 2: Check required environment variables
echo ""
echo "Step 2: Checking required environment variables..."
source .env

# Check MINIO variables
if [ -z "$MINIO_ACCESS_KEY" ] || [ -z "$MINIO_SECRET_KEY" ]; then
    echo "⚠️  WARNING: MINIO credentials not set in .env"
    echo "Using defaults: minioadmin/minioadmin"
    export MINIO_ROOT_USER=minioadmin
    export MINIO_ROOT_PASSWORD=minioadmin
else
    export MINIO_ROOT_USER=$MINIO_ACCESS_KEY
    export MINIO_ROOT_PASSWORD=$MINIO_SECRET_KEY
fi
echo "✅ MinIO credentials configured"

# Check Airflow keys
if [ -z "$AIRFLOW__CORE__FERNET_KEY" ]; then
    echo "⚠️  WARNING: AIRFLOW__CORE__FERNET_KEY not set"
    echo "Using default key (not secure for production!)"
fi
echo "✅ Airflow keys configured"

# Step 3: Clean up any existing containers
echo ""
echo "Step 3: Cleaning up existing containers..."
docker-compose down -v 2>/dev/null || true
echo "✅ Cleanup complete"

# Step 4: Build images
echo ""
echo "Step 4: Building Docker images..."
docker-compose build --no-cache
echo "✅ Images built"

# Step 5: Start infrastructure services first
echo ""
echo "Step 5: Starting infrastructure services..."
docker-compose up -d postgres redis minio
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U airflow > /dev/null 2>&1; do
    echo "  PostgreSQL not ready yet..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Wait for Redis
echo "Waiting for Redis..."
until docker-compose exec -T redis redis-cli -a redis123 ping > /dev/null 2>&1; do
    echo "  Redis not ready yet..."
    sleep 2
done
echo "✅ Redis is ready"

# Wait for MinIO
echo "Waiting for MinIO..."
until curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; do
    echo "  MinIO not ready yet..."
    sleep 2
done
echo "✅ MinIO is ready"

# Step 6: Create MinIO buckets
echo ""
echo "Step 6: Creating MinIO buckets..."
docker-compose up -d createbuckets
sleep 5
echo "✅ Buckets created"

# Step 7: Start MLflow
echo ""
echo "Step 7: Starting MLflow tracking server..."
docker-compose up -d mlflow
echo "⏳ Waiting for MLflow to be ready..."
sleep 15
until curl -f http://localhost:5000/health > /dev/null 2>&1; do
    echo "  MLflow not ready yet..."
    sleep 3
done
echo "✅ MLflow is ready"

# Step 8: Initialize Airflow
echo ""
echo "Step 8: Initializing Airflow..."
docker-compose up -d airflow-init
echo "⏳ Waiting for Airflow initialization..."
docker-compose logs -f airflow-init &
LOGS_PID=$!
sleep 20
kill $LOGS_PID 2>/dev/null || true
echo "✅ Airflow initialized"

# Step 9: Start Airflow services
echo ""
echo "Step 9: Starting Airflow services..."
docker-compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer
echo "⏳ Waiting for Airflow services..."
sleep 20

# Wait for Airflow webserver
echo "Waiting for Airflow webserver..."
until curl -f http://localhost:8081/health > /dev/null 2>&1; do
    echo "  Airflow webserver not ready yet..."
    sleep 3
done
echo "✅ Airflow webserver is ready"

# Step 10: Start remaining services
echo ""
echo "Step 10: Starting remaining services..."
docker-compose up -d model-server nginx prometheus grafana
echo "⏳ Waiting for services to start..."
sleep 10
echo "✅ All services started"

# Step 11: Verify all services
echo ""
echo "Step 11: Verifying all services..."
docker-compose ps

# Step 12: Display access information
echo ""
echo "=========================================="
echo "✅ SYSTEM STARTUP COMPLETE!"
echo "=========================================="
echo ""
echo "Service URLs:"
echo "  🌐 Airflow UI:    http://localhost:8081"
echo "     Username: Cole"
echo "     Password: admin"
echo ""
echo "  📊 MLflow UI:     http://localhost:5000"
echo "  📦 MinIO Console: http://localhost:9001"
echo "     Username: minioadmin"
echo "     Password: minioadmin"
echo ""
echo "  🤖 Model Server:  http://localhost:8000"
echo "  📈 Prometheus:    http://localhost:9090"
echo "  📊 Grafana:       http://localhost:3000"
echo "     Username: admin"
echo "     Password: admin"
echo ""
echo "Next Steps:"
echo "  1. Access Airflow UI at http://localhost:8081"
echo "  2. Enable the 'demand_forecasting_enhanced' DAG"
echo "  3. Trigger a manual run"
echo "  4. Monitor progress in Airflow UI"
echo "  5. View experiment tracking in MLflow UI"
echo ""
echo "To view logs: docker-compose logs -f [service-name]"
echo "To stop all services: docker-compose down"
echo "=========================================="
