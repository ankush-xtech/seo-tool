from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "seo_automation",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.domain_tasks",
        "app.tasks.seo_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,               # Ack only after task completes (safer)
    worker_prefetch_multiplier=1,      # One task at a time per worker slot
    result_expires=86400,              # Results expire after 24h
    task_soft_time_limit=120,          # 2 min soft limit per task
    task_time_limit=180,               # 3 min hard limit
)

# ─── Beat Schedule — Daily Domain Fetch ───────────────────────────────────────
celery_app.conf.beat_schedule = {
    "fetch-new-domains-daily": {
        "task": "app.tasks.domain_tasks.fetch_and_store_domains",
        "schedule": crontab(hour=1, minute=0),   # Every day at 01:00 UTC
        "options": {"queue": "default"},
    },
}
