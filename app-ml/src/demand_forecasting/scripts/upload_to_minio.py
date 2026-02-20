import os
from pathlib import Path

import s3fs

# Get credentials from environment - NO DEFAULTS for production security
ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
KEY = os.environ.get("MINIO_ROOT_USER")
SECRET = os.environ.get("MINIO_ROOT_PASSWORD")
BUCKET = "demand-forecasting"


def upload_data() -> None:
    """Upload data to MinIO S3 storage.

    Requires environment variables:
    - MINIO_ROOT_USER
    - MINIO_ROOT_PASSWORD
    - MINIO_ENDPOINT (optional, defaults to http://minio:9000)
    """
    if not KEY or not SECRET:
        raise ValueError(
            "MinIO credentials must be provided via environment variables: "
            "MINIO_ROOT_USER and MINIO_ROOT_PASSWORD are required"
        )

    fs = s3fs.S3FileSystem(
        client_kwargs={"endpoint_url": ENDPOINT}, key=KEY, secret=SECRET
    )

    local_path = "data/01_raw/raw_data_full.parquet"
    s3_path = f"{BUCKET}/01_raw/raw_data_full.parquet"

    if not Path(local_path).exists():
        return

    if not fs.exists(BUCKET):
        fs.mkdir(BUCKET)

    fs.put(local_path, s3_path)


if __name__ == "__main__":
    upload_data()
