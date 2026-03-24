"""
Domain Celery Tasks
===================
- fetch_and_store_domains   — Daily cron task. Fetches + stores new domains.
- queue_pending_seo_checks  — Dispatches SEO check tasks for pending domains.
"""

import logging
from datetime import date
from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.domain_fetcher import fetch_all_sources, DomainRecord
from app.services.domain_storage import bulk_store_domains
from app.models.models import Domain, DomainStatus

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.tasks.domain_tasks.fetch_and_store_domains",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # Retry after 5 min on failure
)
def fetch_and_store_domains(
    self,
    fetch_date_str: Optional[str] = None,
    triggered_by_user_id: Optional[int] = None,
):
    """
    Main daily task:
      1. Fetch domains from all configured sources
      2. Store new ones in MySQL
      3. Dispatch SEO check tasks for each new domain

    Can be triggered manually via admin dashboard (triggered_by_user_id).
    """
    import asyncio

    target_date = None
    if fetch_date_str:
        try:
            from datetime import datetime
            target_date = datetime.strptime(fetch_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Invalid date format: {fetch_date_str} — using today")

    logger.info(f"[Task] Starting domain fetch for {target_date or date.today()}")

    try:
        # 1. Fetch from all sources (async within sync Celery task)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            records: list[DomainRecord] = loop.run_until_complete(
                fetch_all_sources(target_date)
            )
        finally:
            loop.close()

        if not records:
            logger.warning("[Task] No domains fetched from any source")
            return {"status": "no_data", "domains": 0}

        # 2. Store in DB
        db = SessionLocal()
        try:
            result = bulk_store_domains(db, records, triggered_by_user_id)
        finally:
            db.close()

        logger.info(
            f"[Task] Fetch complete — "
            f"new: {result['new_domains']}, "
            f"skipped: {result['duplicates_skipped']}, "
            f"duration: {result['duration_seconds']}s"
        )

        # 3. Queue SEO checks for newly stored domains
        queue_pending_seo_checks.delay()

        return {
            "status": "success",
            **result,
        }

    except Exception as exc:
        logger.error(f"[Task] fetch_and_store_domains failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.domain_tasks.queue_pending_seo_checks",
    bind=True,
)
def queue_pending_seo_checks(self, limit: int = 5000):
    """
    Reads all domains with check_status=pending and dispatches
    individual SEO check tasks for each one.

    Runs after every fetch, and can also be triggered manually.
    """
    from app.tasks.seo_tasks import run_seo_check_for_domain

    db = SessionLocal()
    try:
        pending = (
            db.query(Domain.id, Domain.name)
            .filter(Domain.check_status == DomainStatus.pending)
            .order_by(Domain.fetched_date.desc(), Domain.id.desc())
            .limit(limit)
            .all()
        )

        if not pending:
            logger.info("[Task] No pending domains to check")
            return {"queued": 0}

        logger.info(f"[Task] Queuing SEO checks for {len(pending)} domains")

        for domain_id, domain_name in pending:
            # Mark as running so we don't queue twice
            db.query(Domain).filter(Domain.id == domain_id).update(
                {"check_status": DomainStatus.running}
            )
            # Dispatch individual SEO task
            run_seo_check_for_domain.delay(domain_id)

        db.commit()
        return {"queued": len(pending)}

    finally:
        db.close()


@celery_app.task(
    name="app.tasks.domain_tasks.manual_fetch",
    bind=True,
    max_retries=1,
)
def manual_fetch(self, user_id: int, fetch_date_str: Optional[str] = None):
    """Admin-triggered manual fetch. Wraps fetch_and_store_domains."""
    return fetch_and_store_domains.apply(
        args=[],
        kwargs={
            "fetch_date_str": fetch_date_str,
            "triggered_by_user_id": user_id,
        },
    ).get()
