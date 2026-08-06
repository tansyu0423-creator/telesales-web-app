from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str

    # .env ファイルから設定を読み込む
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()