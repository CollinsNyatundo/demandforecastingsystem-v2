# =============================================================================
# UPLOAD DATA TO MINIO SCRIPT (PowerShell)
# =============================================================================
# This script uploads local data files to MinIO S3 storage
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Uploading Data to MinIO" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Change to app-ml directory
Set-Location $PSScriptRoot\..

# Check if data directory exists
if (-not (Test-Path "data/01_raw/raw_data_full.parquet")) {
    Write-Host "❌ ERROR: Raw data file not found!" -ForegroundColor Red
    Write-Host "Expected: data/01_raw/raw_data_full.parquet" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Local data files found" -ForegroundColor Green
Write-Host ""

# Install MinIO client in a temporary container
Write-Host "Step 1: Setting up MinIO client..." -ForegroundColor Yellow
docker run --rm --network demand-forecasting-network `
    -v ${PWD}/data:/data `
    minio/mc:latest `
    sh -c "
        mc alias set myminio http://minio:9000 minioadmin minioadmin && `
        mc mb myminio/demand-forecasting --ignore-existing && `
        mc cp --recursive /data/01_raw/ myminio/demand-forecasting/01_raw/ && `
        mc cp --recursive /data/02_intermediate/ myminio/demand-forecasting/02_intermediate/ && `
        mc cp --recursive /data/03_primary/ myminio/demand-forecasting/03_primary/ && `
        mc cp --recursive /data/06_models/ myminio/demand-forecasting/06_models/ && `
        mc ls myminio/demand-forecasting/
    "

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Data uploaded successfully to MinIO!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Uploaded files:" -ForegroundColor White
    Write-Host "  - 01_raw/raw_data_full.parquet" -ForegroundColor Cyan
    Write-Host "  - 02_intermediate/preprocessed_data.parquet" -ForegroundColor Cyan
    Write-Host "  - 03_primary/model_input.parquet" -ForegroundColor Cyan
    Write-Host "  - 06_models/regressor.pickle" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can now run the DAG in Airflow!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ ERROR: Failed to upload data to MinIO" -ForegroundColor Red
    exit 1
}
