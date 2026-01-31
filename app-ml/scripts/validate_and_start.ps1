# =============================================================================
# VALIDATION AND STARTUP SCRIPT (PowerShell)
# =============================================================================
# This script validates the environment and starts all services safely
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Demand Forecasting ML System - Startup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Change to app-ml directory
Set-Location $PSScriptRoot\..

# Step 1: Validate .env file exists
Write-Host "Step 1: Validating environment configuration..." -ForegroundColor Yellow
if (-not (Test-Path .env)) {
    Write-Host "❌ ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please create .env file from .env.template" -ForegroundColor Red
    exit 1
}
Write-Host "✅ .env file found" -ForegroundColor Green

# Step 2: Set environment variables for MinIO
Write-Host ""
Write-Host "Step 2: Setting environment variables..." -ForegroundColor Yellow
$env:MINIO_ROOT_USER = "minioadmin"
$env:MINIO_ROOT_PASSWORD = "minioadmin"
Write-Host "✅ Environment variables set" -ForegroundColor Green

# Step 3: Clean up any existing containers
Write-Host ""
Write-Host "Step 3: Cleaning up existing containers..." -ForegroundColor Yellow
docker-compose down -v 2>$null
Write-Host "✅ Cleanup complete" -ForegroundColor Green

# Step 4: Start infrastructure services first
Write-Host ""
Write-Host "Step 4: Starting infrastructure services..." -ForegroundColor Yellow
docker-compose up -d postgres redis minio
Write-Host "⏳ Waiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Wait for PostgreSQL
Write-Host "Waiting for PostgreSQL..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $result = docker-compose exec -T postgres pg_isready -U airflow 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ PostgreSQL is ready" -ForegroundColor Green
            break
        }
    } catch {}
    Write-Host "  PostgreSQL not ready yet... (attempt $($attempt + 1)/$maxAttempts)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
    $attempt++
}

# Wait for Redis
Write-Host "Waiting for Redis..." -ForegroundColor Yellow
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $result = docker-compose exec -T redis redis-cli -a redis123 ping 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Redis is ready" -ForegroundColor Green
            break
        }
    } catch {}
    Write-Host "  Redis not ready yet... (attempt $($attempt + 1)/$maxAttempts)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
    $attempt++
}

# Wait for MinIO
Write-Host "Waiting for MinIO..." -ForegroundColor Yellow
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9000/minio/health/live" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ MinIO is ready" -ForegroundColor Green
            break
        }
    } catch {}
    Write-Host "  MinIO not ready yet... (attempt $($attempt + 1)/$maxAttempts)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
    $attempt++
}

# Step 5: Create MinIO buckets
Write-Host ""
Write-Host "Step 5: Creating MinIO buckets..." -ForegroundColor Yellow
docker-compose up -d createbuckets
Start-Sleep -Seconds 5
Write-Host "✅ Buckets created" -ForegroundColor Green

# Step 6: Start MLflow
Write-Host ""
Write-Host "Step 6: Starting MLflow tracking server..." -ForegroundColor Yellow
docker-compose up -d mlflow
Write-Host "⏳ Waiting for MLflow to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ MLflow is ready" -ForegroundColor Green
            break
        }
    } catch {}
    Write-Host "  MLflow not ready yet... (attempt $($attempt + 1)/$maxAttempts)" -ForegroundColor Gray
    Start-Sleep -Seconds 3
    $attempt++
}

# Step 7: Initialize Airflow
Write-Host ""
Write-Host "Step 7: Initializing Airflow..." -ForegroundColor Yellow
docker-compose up -d airflow-init
Write-Host "⏳ Waiting for Airflow initialization..." -ForegroundColor Yellow
Start-Sleep -Seconds 30
Write-Host "✅ Airflow initialized" -ForegroundColor Green

# Step 8: Start Airflow services
Write-Host ""
Write-Host "Step 8: Starting Airflow services..." -ForegroundColor Yellow
docker-compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer
Write-Host "⏳ Waiting for Airflow services..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Wait for Airflow webserver
Write-Host "Waiting for Airflow webserver..." -ForegroundColor Yellow
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8081/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Airflow webserver is ready" -ForegroundColor Green
            break
        }
    } catch {}
    Write-Host "  Airflow webserver not ready yet... (attempt $($attempt + 1)/$maxAttempts)" -ForegroundColor Gray
    Start-Sleep -Seconds 3
    $attempt++
}

# Step 9: Start remaining services
Write-Host ""
Write-Host "Step 9: Starting remaining services..." -ForegroundColor Yellow
docker-compose up -d model-server nginx prometheus grafana
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
Write-Host "✅ All services started" -ForegroundColor Green

# Step 10: Verify all services
Write-Host ""
Write-Host "Step 10: Verifying all services..." -ForegroundColor Yellow
docker-compose ps

# Step 11: Display access information
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ SYSTEM STARTUP COMPLETE!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor White
Write-Host "  🌐 Airflow UI:    http://localhost:8081" -ForegroundColor Cyan
Write-Host "     Username: Cole" -ForegroundColor Gray
Write-Host "     Password: admin" -ForegroundColor Gray
Write-Host ""
Write-Host "  📊 MLflow UI:     http://localhost:5000" -ForegroundColor Cyan
Write-Host "  📦 MinIO Console: http://localhost:9001" -ForegroundColor Cyan
Write-Host "     Username: minioadmin" -ForegroundColor Gray
Write-Host "     Password: minioadmin" -ForegroundColor Gray
Write-Host ""
Write-Host "  🤖 Model Server:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  📈 Prometheus:    http://localhost:9090" -ForegroundColor Cyan
Write-Host "  📊 Grafana:       http://localhost:3000" -ForegroundColor Cyan
Write-Host "     Username: admin" -ForegroundColor Gray
Write-Host "     Password: admin" -ForegroundColor Gray
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Access Airflow UI at http://localhost:8081" -ForegroundColor White
Write-Host "  2. Enable the 'demand_forecasting_enhanced' DAG" -ForegroundColor White
Write-Host "  3. Trigger a manual run" -ForegroundColor White
Write-Host "  4. Monitor progress in Airflow UI" -ForegroundColor White
Write-Host "  5. View experiment tracking in MLflow UI" -ForegroundColor White
Write-Host ""
Write-Host "To view logs: docker-compose logs -f [service-name]" -ForegroundColor Gray
Write-Host "To stop all services: docker-compose down" -ForegroundColor Gray
Write-Host "==========================================" -ForegroundColor Cyan
