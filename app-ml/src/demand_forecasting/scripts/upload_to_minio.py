import s3fs
import os

ENDPOINT = "http://minio:9000"  # Accessing host MinIO from Docker
KEY = "minioadmin"
SECRET = "minioadmin"
BUCKET = "demand-forecasting"


def upload_data():
    fs = s3fs.S3FileSystem(
        client_kwargs={"endpoint_url": ENDPOINT}, key=KEY, secret=SECRET
    )

    local_path = "data/01_raw/raw_data_full.parquet"
    s3_path = f"{BUCKET}/01_raw/raw_data_full.parquet"

    if not os.path.exists(local_path):
        print(f"Error: Local file not found at {local_path}")
        return

    if not fs.exists(BUCKET):
        fs.mkdir(BUCKET)

    print(f"Uploading {local_path} to s3://{s3_path}...")
    fs.put(local_path, s3_path)
    print("Upload complete!")


if __name__ == "__main__":
    upload_data()
