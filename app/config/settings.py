import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Application Settings
    APP_ENV: str = Field(default="development", description="Application environment")
    PORT: int = Field(default=8000, description="Port to listen on")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    # AI Provider Settings (Google Gemini)
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", description="Primary Gemini model name (Free Tier)")
    GEMINI_FALLBACK_MODELS: str = Field(default="gemini-2.5-flash-lite,gemini-1.5-flash", description="Comma-separated fallback model names (Free Tier)")
    GEMINI_MAX_RETRIES: int = Field(default=1, description="Max retries per model on rate-limit/quota errors")
    GEMINI_RETRY_DELAY: float = Field(default=2.0, description="Delay in seconds before retrying a model")

    @property
    def gemini_model_chain(self) -> list[str]:
        chain = [self.GEMINI_MODEL]
        if self.GEMINI_FALLBACK_MODELS:
            for m in self.GEMINI_FALLBACK_MODELS.split(","):
                cleaned = m.strip()
                if cleaned and cleaned not in chain:
                    chain.append(cleaned)
        return chain

    # Telegram Bot Settings
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot API Token")

    # Discord Bot Settings
    DISCORD_BOT_TOKEN: str = Field(default="", description="Discord Bot Token")
    DISCORD_APPLICATION_ID: str = Field(default="", description="Discord Application ID")
    DISCORD_PUBLIC_KEY: str = Field(default="", description="Discord Public Key")

    # WhatsApp Cloud API Settings
    WHATSAPP_ACCESS_TOKEN: str = Field(default="", description="WhatsApp Access Token")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="", description="WhatsApp Phone Number ID")
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = Field(default="", description="WhatsApp Business Account ID")
    WHATSAPP_VERIFY_TOKEN: str = Field(default="hirelens_verify_token", description="WhatsApp Webhook Verify Token")
    WHATSAPP_APP_SECRET: str = Field(default="", description="WhatsApp App Secret")

    # Slack Bot Settings
    SLACK_BOT_TOKEN: str = Field(default="", description="Slack Bot Token")
    SLACK_SIGNING_SECRET: str = Field(default="", description="Slack Signing Secret")
    SLACK_APP_TOKEN: str = Field(default="", description="Slack App Token")

    # Database Settings
    DATABASE_URL: str = Field(default="sqlite:///./hirelens.db", description="Database connection URL")

    # Storage & Processing Settings
    MAX_FILE_SIZE_MB: int = Field(default=20, description="Maximum allowed file size in MB")
    TEMP_FILE_DIR: str = Field(default="./temp", description="Directory for temporary uploaded files")
    MAX_CONCURRENT_ANALYSES: int = Field(default=5, description="Max parallel candidate analyses")

    # Scoring Thresholds
    SCORE_STRONG_SHORTLIST: float = 85.0
    SCORE_SHORTLIST: float = 70.0
    SCORE_REVIEW: float = 55.0

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure temp directory exists
os.makedirs(settings.TEMP_FILE_DIR, exist_ok=True)
