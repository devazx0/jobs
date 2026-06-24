import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    gemini_api_key: str = ""
    resend_api_key: str = ""
    email_receiver: str = ""
    daily_cron_hour: int = 9
    daily_cron_timezone: str = "UTC"
    app_env: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
if not settings.database_url:
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        settings.database_url = db_url
