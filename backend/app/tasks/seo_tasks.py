"""
SEO Check Celery Tasks — M3 + M5 (with alert evaluation)
"""

import asyncio
import logging
from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.models import Domain, DomainStatus, SEOResult

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.seo_tasks.run_seo_check_for_domain",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=110,
    time_limit=120,
)
def run_seo_check_for_domain(self, domain_id: int):
    """Runs all SEO checks for a single domain and stores results in DB."""
    db = SessionLocal()
    try:
        domain = db.query(Domain).filter(Domain.id == domain_id).first()
        if not domain:
            logger.warning(f"[SEO Task] Domain {domain_id} not found — skipping")
            return

        logger.info(f"[SEO Task] Checking: {domain.name}")

        from app.services.seo_engine import run_all_checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            check_results = loop.run_until_complete(run_all_checks(domain.name))
        finally:
            loop.close()

        overall_score = check_results.get("overall_score", 0)

        seo_result = SEOResult(
            domain_id=domain.id,
            overall_score=overall_score,
            dns_score=check_results["dns"].get("score"),
            https_score=check_results["https"].get("score"),
            meta_score=check_results["meta"].get("score"),
            robots_score=check_results["robots"].get("score"),
            sitemap_score=check_results["sitemap"].get("score"),
            ssl_score=check_results["ssl"].get("score"),
            speed_score=check_results["speed"].get("score"),
            mobile_score=check_results["mobile"].get("score"),
            social_meta_score=check_results["social_meta"].get("score"),
            heading_score=check_results["headings"].get("score"),
            dns_data=check_results.get("dns"),
            https_data=check_results.get("https"),
            meta_data=check_results.get("meta"),
            robots_data=check_results.get("robots"),
            sitemap_data=check_results.get("sitemap"),
            speed_data=check_results.get("speed"),
            ssl_data=check_results.get("ssl"),
            social_meta_data=check_results.get("social_meta"),
            heading_data=check_results.get("headings"),
        )
        db.add(seo_result)

        domain.seo_score = overall_score
        domain.check_status = DomainStatus.done
        db.commit()

        # ── M5: Evaluate alert rules after every check ────────────────────────
        try:
            from app.services.notification_service import evaluate_alert_rules
            evaluate_alert_rules(db, domain, overall_score)
        except Exception as alert_err:
            logger.warning(f"[SEO Task] Alert evaluation error (non-fatal): {alert_err}")

        logger.info(f"[SEO Task] Done: {domain.name} — score: {overall_score}")
        return {"domain": domain.name, "score": overall_score}

    except Exception as exc:
        logger.error(f"[SEO Task] Failed for domain {domain_id}: {exc}", exc_info=True)
        try:
            db.query(Domain).filter(Domain.id == domain_id).update(
                {"check_status": DomainStatus.failed}
            )
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="app.tasks.seo_tasks.run_seo_check_by_name")
def run_seo_check_by_name(domain_name: str) -> dict:
    """Run SEO check for a domain by name — used from admin API."""
    from datetime import datetime, timezone
    db = SessionLocal()
    try:
        domain = db.query(Domain).filter(Domain.name == domain_name).first()
        if not domain:
            tld = domain_name.split(".")[-1] if "." in domain_name else ""
            domain = Domain(
                name=domain_name,
                tld=tld,
                check_status=DomainStatus.running,
                fetched_date=datetime.now(timezone.utc),
            )
            db.add(domain)
            db.commit()
            db.refresh(domain)
        run_seo_check_for_domain.apply(args=[domain.id])
        return {"status": "completed", "domain": domain_name}
    finally:
        db.close()
