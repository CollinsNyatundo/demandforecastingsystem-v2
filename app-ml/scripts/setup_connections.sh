#!/bin/bash
# Setup Airflow Connections for MinIO and Email
# This script should be run inside the airflow-scheduler container

set -e

echo "Setting up Airflow connections..."

# MinIO S3 Connection for Remote Logging
airflow connections delete 'minio_s3' 2>/dev/null || true
airflow connections add 'minio_s3' \
    --conn-type 's3' \
    --conn-host 'minio:9000' \
    --conn-login 'minioadmin' \
    --conn-password 'minioadmin' \
    --conn-extra '{
        "endpoint_url": "http://minio:9000",
        "aws_access_key_id": "minioadmin",
        "aws_secret_access_key": "minioadmin"
    }'

echo "✅ MinIO S3 connection created: minio_s3"

# Create airflow-logs bucket in MinIO for remote logging
echo "Creating airflow-logs bucket in MinIO..."
docker-compose exec -T minio sh -c "
    mc alias set myminio http://localhost:9000 minioadmin minioadmin 2>/dev/null
    mc mb myminio/airflow-logs 2>/dev/null || echo 'Bucket already exists'
    echo '✅ airflow-logs bucket ready'
"

echo ""
echo "=========================================="
echo "Airflow Connections Setup Complete!"
echo "=========================================="
echo ""
echo "📝 Next Steps:"
echo "1. Copy .env.template to .env"
echo "2. Add your Gmail App Password to .env"
echo "3. Restart services: docker-compose restart"
echo ""
echo "To verify connections:"
echo "  docker-compose exec airflow-scheduler airflow connections list"
echo ""
