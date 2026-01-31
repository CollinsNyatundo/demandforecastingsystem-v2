import s3fs
import os

def migrate_data():
    fs = s3fs.S3FileSystem(
        client_kwargs={'endpoint_url': 'http://127.0.0.1:9000'},

        # Wait, previous commands used 9000. User specified --console-address ":9001".
        # So API is likely 9000.
        key='minioadmin',
        secret='minioadmin'
    )

    # Ensure bucket exists
    if not fs.exists('demand-forecasting'):
        fs.mkdir('demand-forecasting')
        print("Created bucket 'demand-forecasting'")

    local_root = "data"
    s3_root = "demand-forecasting"

    # Walk through local data directory
    for root, dirs, files in os.walk(local_root):
        for file in files:
            local_path = os.path.join(root, file)
            # Create S3 path preserving structure, e.g., data/01_raw/file.parquet -> demand-forecasting/01_raw/file.parquet
            rel_path = os.path.relpath(local_path, local_root)
            # Fix path separator for S3
            rel_path_s3 = rel_path.replace("\\", "/")
            s3_path = f"{s3_root}/{rel_path_s3}"
            
            print(f"Uploading {local_path} to s3://{s3_path}")
            try:
                fs.put(local_path, s3_path)
            except Exception as e:
                print(f"Failed to upload {local_path}: {e}")

if __name__ == "__main__":
    # Force API port 9000 based on standard MinIO
    migrate_data()
