import boto3
from botocore.client import Config
import sys

s3 = boto3.client('s3',
                    endpoint_url='http://minio:9000',
                    aws_access_key_id='minioadmin',
                    aws_secret_access_key='minioadmin',
                    config=Config(signature_version='s3v4'),
                    region_name='us-east-1')

BUCKET = 'demand-forecasting' 

try:
    print("Listing objects in demand-forecasting bucket:")
    objects = s3.list_objects_v2(Bucket=BUCKET)
    if 'Contents' in objects:
        for obj in objects['Contents']:
            print(f"- {obj['Key']}")
    else:
        print("Bucket is empty.")

except Exception as e:
    print(f"Error reading bucket: {e}")
