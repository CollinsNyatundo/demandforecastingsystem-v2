
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

BUCKET = "demand-forecasting"

try:
    objects = s3.list_objects_v2(Bucket=BUCKET)
    if "Contents" in objects:
        for _obj in objects["Contents"]:
            pass
    else:
        pass

except Exception:
    pass
