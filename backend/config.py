import os
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/telesales_db"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "telesales-audio"
    minio_secure: bool = False

    groq_api_key: str = ""

    # .env ファイルから設定を読み込む（開発環境・テスト環境のパスに対応）
    model_config = SettingsConfigDict(
        env_file=(os.path.join(BASE_DIR, ".env"), ".env"),
        extra="ignore"
    )

settings = Settings()