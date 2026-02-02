from pathlib import Path
import s3fs

ENDPOINT = "http://minio:9000"  # Accessing host MinIO from Docker
KEY = "minioadmin"
SECRET = "minioadmin"
BUCKET = "demand-forecasting"


def upload_data():
    """Upload data to MinIO S3 storage."""
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
