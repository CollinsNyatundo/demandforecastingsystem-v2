import sys

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

BUCKET = "airflow-logs"

try:
    # List objects to find the latest log
    objects = s3.list_objects_v2(Bucket=BUCKET)
    if "Contents" not in objects:
        sys.exit(0)

    # Sort by LastModified to get latest
    latest_obj = sorted(
        objects["Contents"], key=lambda obj: obj["LastModified"], reverse=True
    )[0]
    key = latest_obj["Key"]

    response = s3.get_object(Bucket=BUCKET, Key=key)
    log_content = response["Body"].read().decode("utf-8")

except Exception:
    pass
