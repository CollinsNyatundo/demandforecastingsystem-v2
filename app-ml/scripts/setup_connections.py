#!/usr/bin/env python3
"""Setup Airflow Connections for MinIO and Remote Logging
Run this script inside the airflow-scheduler container.
"""

import subprocess
import sys


def run_command(cmd, check=True) -> bool:
    """Run a command and return the result."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return not (check and result.returncode != 0)


def delete_connection(conn_id):
    """Delete an existing connection if it exists."""
    cmd = ["airflow", "connections", "delete", conn_id]
    run_command(cmd, check=False)


def create_minio_connection() -> bool:
    """Create MinIO S3 connection for remote logging."""
    # Delete existing connection
    delete_connection("minio_s3")

    # Create new connection
    cmd = [
        "airflow",
        "connections",
        "add",
        "minio_s3",
        "--conn-type",
        "s3",
        "--conn-host",
        "minio:9000",
        "--conn-login",
        "minioadmin",
        "--conn-password",
        "minioadmin",
        "--conn-extra",
        '{"endpoint_url": "http://minio:9000", "aws_access_key_id": "minioadmin", "aws_secret_access_key": "minioadmin"}',
    ]

    return bool(run_command(cmd))


def create_airflow_logs_bucket() -> bool:
    """Create airflow-logs bucket in MinIO."""
    # Use mc (MinIO Client) to create bucket
    cmd = [
        "sh",
        "-c",
        "mc alias set myminio http://minio:9000 minioadmin minioadmin 2>/dev/null && "
        "mc mb myminio/airflow-logs 2>/dev/null || echo 'Bucket already exists'",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return bool("already exists" in result.stdout or result.returncode == 0)


def verify_connections() -> bool:
    """Verify connections were created."""
    cmd = ["airflow", "connections", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    return "minio_s3" in result.stdout


def main() -> int:
    """Main setup function."""
    success = True

    # Create MinIO S3 connection
    if not create_minio_connection():
        success = False

    # Create airflow-logs bucket
    create_airflow_logs_bucket()

    # Verify
    if not verify_connections():
        success = False

    if success:
        pass
    else:
        pass

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
