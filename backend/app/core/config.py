from pydantic_settings import BaseSettings
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    # App
    APP_NAME: str = "SEO Automation Tool"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "seo_automation"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS — allow all origins in dev so localhost:5173 always works
    ALLOWED_ORIGINS: str = "*"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        raw = self.ALLOWED_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM: str = "noreply@yourdomain.com"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    SEO_CHECK_RATE_LIMIT: int = 10

    # Admin bootstrap
    FIRST_ADMIN_EMAIL: str = "admin@yourdomain.com"
    FIRST_ADMIN_PASSWORD: str = "Admin@123!"

    # Monitoring
    SENTRY_DSN: Optional[str] = None

    # Domain Fetcher
    DOMAINBIGDATA_API_KEY: Optional[str] = None
    ICANN_CZDS_TOKEN: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
