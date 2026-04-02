from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

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
    SEO_CHECK_RATE_LIMIT: int = 50

    # Admin bootstrap
    FIRST_ADMIN_EMAIL: str = "admin@yourdomain.com"
    FIRST_ADMIN_PASSWORD: str = "Admin@123!"

    # Monitoring
    SENTRY_DSN: Optional[str] = None

    # Domain Fetcher
    DOMAINBIGDATA_API_KEY: Optional[str] = None
    ICANN_CZDS_TOKEN: Optional[str] = None

    # Google Maps / SerpAPI
    SERPAPI_KEY: Optional[str] = None
    MAPS_SCRAPE_DELAY: float = 1.5
    MAPS_EMAIL_SCRAPE_DELAY: float = 1.0
    MAPS_MAX_RESULTS: int = 60
    MAPS_WORKER_THREADS: int = 5

    # Outreach / SendGrid
    SENDGRID_API_KEY: Optional[str] = None
    OUTREACH_FROM_EMAIL: str = "hello@youragency.com"
    OUTREACH_FROM_NAME: str = "SEO Agency"
    OUTREACH_SCORE_THRESHOLD: int = 70
    OUTREACH_SEO_WORKERS: int = 5

    # AI provider keys
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    AI_EMAIL_MODEL: str = "claude-haiku-4-5"

    # Semrush API
    SEMRUSH_API_KEY: Optional[str] = None
    SEMRUSH_DATABASE: str = "au"

    # Competitor Analysis
    COMPETITOR_MAX_RESULTS: int = 10
    COMPETITOR_WORKER_THREADS: int = 3


settings = Settings()
