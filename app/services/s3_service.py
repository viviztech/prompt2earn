import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

CATEGORY_RULES = {
    "poster": {"types": ["image/jpeg", "image/png", "image/webp"], "exts": ["jpg", "jpeg", "png", "webp"], "max_mb": 10},
    "video": {"types": ["video/mp4", "video/quicktime", "video/webm"], "exts": ["mp4", "mov", "webm"], "max_mb": 500},
    "audio": {"types": ["audio/mpeg", "audio/wav", "audio/ogg"], "exts": ["mp3", "wav", "ogg"], "max_mb": 50},
    "caption": {"types": ["text/plain", "application/pdf"], "exts": ["txt", "pdf"], "max_mb": 2},
}


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def generate_s3_key(user_id: str, prompt_id: str, ext: str) -> str:
    now = datetime.utcnow()
    file_uuid = uuid.uuid4().hex
    return f"submissions/{now.year}/{now.month:02d}/{user_id}/{prompt_id}/{file_uuid}.{ext}"


def create_presigned_post(category_name: str, user_id: str, prompt_id: str, filename: str, content_type: str) -> dict:
    rules = CATEGORY_RULES.get(category_name)
    if not rules:
        raise ValueError(f"Unknown category: {category_name}")

    if content_type not in rules["types"]:
        raise ValueError(f"File type {content_type} not allowed for {category_name}")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in rules["exts"]:
        raise ValueError(f"File extension .{ext} not allowed for {category_name}")

    max_bytes = rules["max_mb"] * 1024 * 1024
    s3_key = generate_s3_key(user_id, prompt_id, ext)

    client = get_s3_client()
    try:
        response = client.generate_presigned_post(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=300,
        )
        return {"url": response["url"], "fields": response["fields"], "key": s3_key}
    except ClientError as e:
        logger.error(f"S3 presign error: {e}")
        raise


def create_presigned_get_url(s3_key: str, expiry_seconds: int = 900) -> str:
    client = get_s3_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )
    except ClientError as e:
        logger.error(f"S3 get presign error: {e}")
        return ""


def delete_s3_object(s3_key: str) -> bool:
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        logger.error(f"S3 delete error: {e}")
        return False
