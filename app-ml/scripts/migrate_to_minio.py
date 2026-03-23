import contextlib
import os

import s3fs


def migrate_data():
    """Migrate local data to MinIO S3 storage.
    
    Requires environment variables:
    - MINIO_ROOT_USER
    - MINIO_ROOT_PASSWORD
    - MINIO_ENDPOINT (optional, defaults to http://127.0.0.1:9000)
    """
    import os
    
    key = os.environ.get("MINIO_ROOT_USER")
    secret = os.environ.get("MINIO_ROOT_PASSWORD")
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://127.0.0.1:9000")
    
    if not key or not secret:
        raise ValueError(
            "MinIO credentials must be provided via environment variables: "
            "MINIO_ROOT_USER and MINIO_ROOT_PASSWORD are required"
        )
    
    fs = s3fs.S3FileSystem(
        client_kwargs={"endpoint_url": endpoint},
        key=key,
        secret=secret,
    )

    # Ensure bucket exists
    if not fs.exists("demand-forecasting"):
        fs.mkdir("demand-forecasting")

    local_root = "data"
    s3_root = "demand-forecasting"

    # Walk through local data directory
    for root, _dirs, files in os.walk(local_root):
        for file in files:
            local_path = os.path.join(root, file)
            # Create S3 path preserving structure, e.g., data/01_raw/file.parquet -> demand-forecasting/01_raw/file.parquet
            rel_path = os.path.relpath(local_path, local_root)
            # Fix path separator for S3
            rel_path_s3 = rel_path.replace("\\", "/")
            s3_path = f"{s3_root}/{rel_path_s3}"

            with contextlib.suppress(Exception):
                fs.put(local_path, s3_path)


if __name__ == "__main__":
    # Force API port 9000 based on standard MinIO
    migrate_data()
