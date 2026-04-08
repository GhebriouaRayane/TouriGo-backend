import secrets
from typing import List, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "TouriGo API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 jours
    GOOGLE_CLIENT_ID: str | None = None

    DATABASE_URL: str = "postgresql://user:pass@localhost/db"
    REGISTRATION_CODE_LENGTH: int = 6
    REGISTRATION_CODE_EXPIRE_MINUTES: int = 10
    REGISTRATION_CODE_MAX_ATTEMPTS: int = 5
    AUTH_EXPOSE_DEBUG_CODE: bool = False

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True
    RESEND_API_KEY: str | None = None
    BREVO_API_KEY: str | None = None
    INFOBIP_API_KEY: str | None = None
    INFOBIP_BASE_URL: str | None = None
    INFOBIP_SENDER: str | None = None
    SMTP_USE_SSL: bool = False
    RESEND_API_KEY: str | None = None
    BREVO_API_KEY: str | None = None

    SMS_WEBHOOK_URL: str | None = None
    SMS_WEBHOOK_TOKEN: str | None = None

    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_STORAGE_BUCKET: str | None = None
    SUPABASE_STORAGE_AVATARS_PREFIX: str = "avatars"
    SUPABASE_STORAGE_LISTINGS_PREFIX: str = "listings"

    ALLOWED_HOSTS: List[str] = [
        "*",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    AUTO_CREATE_TABLES: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )

settings = Settings()
