import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(
        default="mock_bot_token_for_tests",
        description="Telegram Bot API Token from @BotFather"
    )
    OWNER_SETUP_CODE: str = Field(
        default="sakura_owner_secret_998877_setup",
        description="One-time secret token for claiming shop ownership"
    )
    WEBAPP_URL: str = Field(
        default="http://localhost:8000",
        description="Base URL where the Mini App is served"
    )
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./sakura_shop.db",
        description="SQLAlchemy async database URL"
    )
    DEV_ADMIN_ID: Optional[int] = Field(
        default=None,
        description="Optional developer Telegram user ID for local testing"
    )
    DEV_BROWSER_MODE: bool = Field(
        default=False,
        description="Local only: accept the fake 'dev_browser_mode' initData as owner. Never enable in production."
    )
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    MEDIA_CACHE_DIR: str = Field(default="./media_cache")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
