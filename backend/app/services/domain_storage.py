"""
Domain Storage Service
======================
Handles bulk inserting fetched domains into MySQL with:
  - Deduplication against existing records
  - Batch upsert for performance
  - Fetch run logging
"""

import logging
from datetime import date, datetime, timezone
from typing import TypedDict

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.models.models import Domain, DomainStatus, AuditLog, AuditAction
from app.services.domain_fetcher import DomainRecord

logger = logging.getLogger(__name__)

BATCH_SIZE = 500   # Insert N rows per batch


class FetchRunResult(TypedDict):
    date: str
    total_fetched: int
    new_domains: int
    duplicates_skipped: int
    duration_seconds: float


def bulk_store_domains(
    db: Session,
    records: list[DomainRecord],
    triggered_by_user_id: int | None = None,
) -> FetchRunResult:
    """
    Stores a list of DomainRecord objects into the DB.
    Skips any domain already stored for today (dedup by name).
    Returns a summary of what was inserted.
    """
    import time
    start = time.time()

    if not records:
        return FetchRunResult(
            date=str(date.today()),
            total_fetched=0,
            new_domains=0,
            duplicates_skipped=0,
            duration_seconds=0.0,
        )

    fetch_date = datetime.now(timezone.utc)
    total_fetched = len(records)

    # ── Get existing domain names from DB to deduplicate ──────────────────────
    existing_names: set[str] = set()
    # Query in chunks to avoid huge IN clauses
    all_names = [r.name for r in records]
    for i in range(0, len(all_names), 1000):
        chunk = all_names[i:i + 1000]
        rows = db.execute(
            select(Domain.name).where(Domain.name.in_(chunk))
        ).scalars().all()
        existing_names.update(rows)

    new_records = [r for r in records if r.name not in existing_names]
    duplicates_skipped = total_fetched - len(new_records)

    logger.info(
        f"[Storage] {total_fetched:,} fetched | "
        f"{len(new_records):,} new | {duplicates_skipped:,} duplicates"
    )

    # ── Batch insert new domains ───────────────────────────────────────────────
    inserted = 0
    for i in range(0, len(new_records), BATCH_SIZE):
        batch = new_records[i:i + BATCH_SIZE]
        rows = [
            {
                "name": r.name,
                "tld": r.tld,
                "registrar": r.registrar,
                "registered_at": r.registered_at,
                "fetched_date": fetch_date,
                "check_status": DomainStatus.pending,
                "is_active": True,
            }
            for r in batch
        ]

        # Use INSERT IGNORE to handle any race conditions
        stmt = mysql_insert(Domain).values(rows).prefix_with("IGNORE")
        result = db.execute(stmt)
        db.flush()
        inserted += result.rowcount
        logger.debug(f"[Storage] Inserted batch {i // BATCH_SIZE + 1}: {result.rowcount} rows")

    db.commit()

    duration = round(time.time() - start, 2)

    # ── Audit log ─────────────────────────────────────────────────────────────
    db.add(AuditLog(
        user_id=triggered_by_user_id,
        action=AuditAction.fetch_domains,
        description=f"Domain fetch run: {inserted} new domains stored",
        meta={
            "total_fetched": total_fetched,
            "new_domains": inserted,
            "duplicates_skipped": duplicates_skipped,
            "duration_seconds": duration,
        },
    ))
    db.commit()

    return FetchRunResult(
        date=str(date.today()),
        total_fetched=total_fetched,
        new_domains=inserted,
        duplicates_skipped=duplicates_skipped,
        duration_seconds=duration,
    )


def get_domain_stats(db: Session) -> dict:
    """Returns aggregate stats about domains in the DB."""
    total = db.query(func.count(Domain.id)).scalar()
    today_count = db.query(func.count(Domain.id)).filter(
        func.date(Domain.fetched_date) == date.today()
    ).scalar()
    pending = db.query(func.count(Domain.id)).filter(
        Domain.check_status == DomainStatus.pending
    ).scalar()
    done = db.query(func.count(Domain.id)).filter(
        Domain.check_status == DomainStatus.done
    ).scalar()
    avg_score = db.query(func.avg(Domain.seo_score)).filter(
        Domain.seo_score.isnot(None)
    ).scalar()

    return {
        "total_domains": total or 0,
        "fetched_today": today_count or 0,
        "pending_check": pending or 0,
        "checked": done or 0,
        "avg_seo_score": round(float(avg_score), 1) if avg_score else None,
    }
