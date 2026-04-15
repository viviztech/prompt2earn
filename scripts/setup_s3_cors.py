"""
Run this once to configure CORS on the S3 bucket so browsers can upload directly.
Usage: python scripts/setup_s3_cors.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import boto3
from app.config import get_settings

settings = get_settings()

cors_configuration = {
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["POST", "PUT", "GET"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3000,
        }
    ]
}

client = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)

client.put_bucket_cors(
    Bucket=settings.AWS_S3_BUCKET,
    CORSConfiguration=cors_configuration,
)
print(f"CORS configured on bucket: {settings.AWS_S3_BUCKET}")

# Verify
resp = client.get_bucket_cors(Bucket=settings.AWS_S3_BUCKET)
print("Current CORS rules:", resp["CORSRules"])
