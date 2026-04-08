from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "PromptEarn"
    SECRET_KEY: str
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = "prompt-to-earn-submissions"
    AWS_REGION: str = "ap-south-1"

    MAIL_HOST: str = "smtp.gmail.com"
    MAIL_PORT: int = 465
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""

    MINIMUM_REDEMPTION_POINTS: int = 500
    POINTS_PER_INR: int = 1
    POINTS_EXPIRY_DAYS: int = 180

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
