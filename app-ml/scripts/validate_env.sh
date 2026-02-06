#!/bin/bash
# Environment Variable Validation Script
# Run before deployment to ensure all required variables are set

set -e

echo "=================================="
echo "Environment Variable Validation"
echo "=================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track validation status
ERRORS=0

# Required environment variables
REQUIRED_VARS=(
    # MinIO/S3
    "MINIO_ACCESS_KEY"
    "MINIO_SECRET_KEY"
    "MINIO_ENDPOINT_URL"
    
    # MLflow
    "MLFLOW_TRACKING_URI"
    
    # PostgreSQL
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "POSTGRES_DB"
    
    # Airflow
    "AIRFLOW__CORE__SQL_ALCHEMY_CONN"
    "AIRFLOW__WEBSERVER__SECRET_KEY"
)

# Optional but recommended variables
RECOMMENDED_VARS=(
    "REDIS_HOST"
    "REDIS_PASSWORD"
    "OPTUNA_STORAGE_URL"
    "GRAFANA_ADMIN_PASSWORD"
)

echo ""
echo "Checking required variables..."
echo "------------------------------"

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}✗ MISSING: $var${NC}"
        ERRORS=$((ERRORS + 1))
    else
        # Mask sensitive values
        if [[ "$var" == *"PASSWORD"* ]] || [[ "$var" == *"SECRET"* ]] || [[ "$var" == *"KEY"* ]]; then
            echo -e "${GREEN}✓ SET: $var = ****${NC}"
        else
            echo -e "${GREEN}✓ SET: $var = ${!var}${NC}"
        fi
    fi
done

echo ""
echo "Checking recommended variables..."
echo "---------------------------------"

for var in "${RECOMMENDED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${YELLOW}⚠ NOT SET: $var (optional)${NC}"
    else
        if [[ "$var" == *"PASSWORD"* ]] || [[ "$var" == *"SECRET"* ]]; then
            echo -e "${GREEN}✓ SET: $var = ****${NC}"
        else
            echo -e "${GREEN}✓ SET: $var = ${!var}${NC}"
        fi
    fi
done

echo ""
echo "=================================="

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}FAILED: $ERRORS required variable(s) missing${NC}"
    echo "Please set the missing variables before deployment."
    exit 1
else
    echo -e "${GREEN}SUCCESS: All required variables are set${NC}"
    exit 0
fi
