# Start all services for Demand Forecasting MLOps System
Write-Host "Starting all services for Demand Forecasting MLOps System..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

# Navigate to app-ml directory
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Step 1: Checking current service status..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "Step 2: Starting/Restarting Airflow Worker..." -ForegroundColor Yellow
docker-compose up -d airflow-worker

Write-Host ""
Write-Host "Step 3: Waiting for services to stabilize..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "Step 4: Starting Nginx..." -ForegroundColor Yellow
docker-compose up -d nginx

Write-Host ""
Write-Host "Step 5: Starting Prometheus..." -ForegroundColor Yellow
docker-compose up -d prometheus

Write-Host ""
Write-Host "Step 6: Starting Grafana..." -ForegroundColor Yellow
docker-compose up -d grafana

Write-Host ""
Write-Host "Step 7: Waiting for all services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "All services started! Checking final status..." -ForegroundColor Green
Write-Host ""
docker-compose ps

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  - Airflow UI: http://localhost:8081 (Cole/admin)" -ForegroundColor White
Write-Host "  - MLflow UI: http://localhost:5000" -ForegroundColor White
Write-Host "  - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)" -ForegroundColor White
Write-Host "  - Model Server: http://localhost:8000" -ForegroundColor White
Write-Host "  - Model Server Metrics: http://localhost:8001" -ForegroundColor White
Write-Host "  - Prometheus: http://localhost:9090" -ForegroundColor White
Write-Host "  - Grafana: http://localhost:3000 (admin/admin)" -ForegroundColor White
Write-Host "  - Nginx: http://localhost:80" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
