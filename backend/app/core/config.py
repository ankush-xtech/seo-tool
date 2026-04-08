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
    # Public URL of this backend — used to embed open/click tracking in emails.
    # Example: http://yourserver.com:8000  or  https://api.yourdomain.com
    # Leave blank to disable tracking (emails still send fine without it).
    TRACKING_BASE_URL: Optional[str] = None
    OUTREACH_FROM_NAME: str = "SEO Agency"
    OUTREACH_SCORE_THRESHOLD: int = 70
    OUTREACH_SEO_WORKERS: int = 5

    # Company branding — shown in both template and AI emails
    COMPANY_NAME: str = "Sparksview"
    COMPANY_COUNTRY: str = "Australia"
    COMPANY_SPECIALIZATION: str = "SEO and digital growth solutions"
    COMPANY_EMAIL: str = "devadmin@sparkview.com.au"
    COMPANY_WEBSITE: str = "www.sparkview.com.au"
    COMPANY_TYPE: str = "IT company"
    # Static subject line — same for ALL outreach emails (AI + template)
    OUTREACH_SUBJECT: str = "Free SEO Audit Insights for Your Website"

    # Claude AI (Anthropic) — for AI-generated email content
    ANTHROPIC_API_KEY: Optional[str] = None
    # Model for email generation. Default: claude-haiku-4-5 (cheap, fast).
    # Use claude-opus-4-6 for highest quality (more expensive).
    AI_EMAIL_MODEL: str = "claude-haiku-4-5"

    # Groq AI — free alternative for AI email generation
    # Get free key at: https://console.groq.com
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Outreach / SendGrid
    SENDGRID_API_KEY: Optional[str] = None
    OUTREACH_FROM_EMAIL: str = "hello@youragency.com"
    # Public URL of this backend — used to embed open/click tracking in emails.
    # Example: http://yourserver.com:8000  or  https://api.yourdomain.com
    # Leave blank to disable tracking (emails still send fine without it).
    TRACKING_BASE_URL: Optional[str] = None
    OUTREACH_FROM_NAME: str = "SEO Agency"
    OUTREACH_SCORE_THRESHOLD: int = 70
    OUTREACH_SEO_WORKERS: int = 5

    # Company branding — shown in both template and AI emails
    COMPANY_NAME: str = "Sparksview"
    COMPANY_COUNTRY: str = "Australia"
    COMPANY_SPECIALIZATION: str = "SEO and digital growth solutions"
    COMPANY_EMAIL: str = "devadmin@sparkview.com.au"
    COMPANY_WEBSITE: str = "www.sparkview.com.au"
    COMPANY_TYPE: str = "IT company"
    # Static subject line — same for ALL outreach emails (AI + template)
    OUTREACH_SUBJECT: str = "Free SEO Audit Insights for Your Website"

    # Claude AI (Anthropic) — for AI-generated email content
    ANTHROPIC_API_KEY: Optional[str] = None
    # Model for email generation. Default: claude-haiku-4-5 (cheap, fast).
    # Use claude-opus-4-6 for highest quality (more expensive).
    AI_EMAIL_MODEL: str = "claude-haiku-4-5"

    # Groq AI — free alternative for AI email generation
    # Get free key at: https://console.groq.com
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

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


settings = Settings()
