import boto3
from botocore.client import Config

s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

try:
    s3.create_bucket(Bucket="airflow-logs")
    print("Bucket 'airflow-logs' created successfully.")
except s3.exceptions.BucketAlreadyOwnedByYou:
    print("Bucket 'airflow-logs' already exists.")
except Exception as e:
    print(f"Error creating bucket: {e}")
