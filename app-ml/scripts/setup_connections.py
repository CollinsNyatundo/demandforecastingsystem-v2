#!/usr/bin/env python3
"""
Setup Airflow Connections for MinIO and Remote Logging
Run this script inside the airflow-scheduler container
"""

import subprocess
import sys


def run_command(cmd, check=True):
    """Run a command and return the result"""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        return False
    return True


def delete_connection(conn_id):
    """Delete an existing connection if it exists"""
    print(f"Checking for existing connection: {conn_id}")
    cmd = ["airflow", "connections", "delete", conn_id]
    run_command(cmd, check=False)


def create_minio_connection():
    """Create MinIO S3 connection for remote logging"""
    print("\n📦 Creating MinIO S3 connection...")

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

    if run_command(cmd):
        print("✅ MinIO S3 connection created: minio_s3")
        return True
    else:
        print("❌ Failed to create MinIO S3 connection")
        return False


def create_airflow_logs_bucket():
    """Create airflow-logs bucket in MinIO"""
    print("\n📦 Creating airflow-logs bucket in MinIO...")

    # Use mc (MinIO Client) to create bucket
    cmd = [
        "sh",
        "-c",
        "mc alias set myminio http://minio:9000 minioadmin minioadmin 2>/dev/null && "
        "mc mb myminio/airflow-logs 2>/dev/null || echo 'Bucket already exists'",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if "already exists" in result.stdout or result.returncode == 0:
        print("✅ airflow-logs bucket ready")
        return True
    else:
        print(
            "⚠️  Could not create bucket (may need to run manually in minio container)"
        )
        return False


def verify_connections():
    """Verify connections were created"""
    print("\n🔍 Verifying connections...")
    cmd = ["airflow", "connections", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if "minio_s3" in result.stdout:
        print("✅ Connection verified: minio_s3")
        return True
    else:
        print("❌ Connection not found")
        return False


def main():
    """Main setup function"""
    print("=" * 60)
    print("   Airflow Connections Setup")
    print("=" * 60)
    print()

    success = True

    # Create MinIO S3 connection
    if not create_minio_connection():
        success = False

    # Create airflow-logs bucket
    create_airflow_logs_bucket()

    # Verify
    if not verify_connections():
        success = False

    print()
    print("=" * 60)
    if success:
        print("✅ Airflow Connections Setup Complete!")
    else:
        print("⚠️  Setup completed with warnings")
    print("=" * 60)
    print()
    print("📝 Next Steps:")
    print("1. Copy .env.template to .env")
    print("2. Add your Gmail App Password to .env")
    print("3. Restart services: docker-compose restart")
    print()
    print("To verify connections:")
    print("  docker-compose exec airflow-scheduler airflow connections list")
    print()
    print("To create airflow-logs bucket manually (if needed):")
    print(
        '  docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc mb myminio/airflow-logs"'
    )
    print()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
