from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.db.session import Base, engine, check_db_connection
from app.routers import auth, users, domains, seo, dashboard, watchlist, alerts, reports

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def init_sentry():
    sentry_dsn = getattr(settings, "SENTRY_DSN", None)
    if sentry_dsn and settings.APP_ENV == "production":
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            sentry_sdk.init(
                dsn=sentry_dsn,
                environment=settings.APP_ENV,
                integrations=[FastApiIntegration(), SqlalchemyIntegration()],
                traces_sample_rate=0.1,
            )
            logger.info("Sentry initialized")
        except ImportError:
            logger.warning("sentry-sdk not installed — skipping Sentry init")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} [{settings.APP_ENV}]")
    init_sentry()
    if check_db_connection():
        logger.info("✅ Database connected")
        Base.metadata.create_all(bind=engine)
        bootstrap_admin()
    else:
        logger.error("❌ Database connection failed!")
    yield
    logger.info("Shutting down...")


def bootstrap_admin():
    from app.db.session import SessionLocal
    from app.models.models import User, UserRole
    from app.core.security import hash_password
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.FIRST_ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                email=settings.FIRST_ADMIN_EMAIL,
                full_name="System Admin",
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                role=UserRole.admin,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            db.commit()
            logger.info(f"✅ Admin user created: {settings.FIRST_ADMIN_EMAIL}")
    finally:
        db.close()


app = FastAPI(
    title=settings.APP_NAME,
    description="SEO Automation Tool API",
    version="1.0.0",
    docs_url="/api/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/api/redoc" if settings.APP_ENV != "production" else None,
    openapi_url="/api/openapi.json" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    detail = "; ".join(f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "detail": detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"success": False, "detail": "Internal server error"})


app.include_router(auth.router,      prefix="/api/v1")
app.include_router(users.router,     prefix="/api/v1")
app.include_router(domains.router,   prefix="/api/v1")
app.include_router(seo.router,       prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(alerts.router,    prefix="/api/v1")
app.include_router(reports.router,   prefix="/api/v1")


@app.get("/api/health", tags=["Health"])
def health_check():
    db_ok = check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "db": "connected" if db_ok else "unreachable",
        "version": "1.0.0",
    }


@app.get("/", include_in_schema=False)
def root():
    return {"message": f"{settings.APP_NAME} API is running."}
