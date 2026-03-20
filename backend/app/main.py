from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.db.session import Base, engine, check_db_connection
from app.routers import auth, users, domains, seo, dashboard, watchlist, alerts, reports

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} [{settings.APP_ENV}]")

    if check_db_connection():
        logger.info("✅ Database connected")
        # Create tables if they don't exist (use Alembic in production)
        Base.metadata.create_all(bind=engine)
        # Bootstrap admin user if not exists
        bootstrap_admin()
    else:
        logger.error("❌ Database connection failed!")

    yield
    # Shutdown
    logger.info("Shutting down...")


def bootstrap_admin():
    """Create default admin account on first run."""
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


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="SEO Automation Tool API — daily domain fetcher + SEO analysis engine",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception Handlers ───────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    detail = "; ".join(
        f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in errors
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "detail": detail}
    )


# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(domains.router, prefix="/api/v1")
app.include_router(seo.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
def health_check():
    db_ok = check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "db": "connected" if db_ok else "unreachable",
    }


@app.get("/", include_in_schema=False)
def root():
    return {"message": f"{settings.APP_NAME} API is running. Visit /api/docs"}
