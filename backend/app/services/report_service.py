"""
Report Service
==============
Generates exportable reports:
  - CSV domain list with SEO scores
  - CSV SEO audit report (per domain check breakdown)
  - PDF summary report
"""

import csv
import io
import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Domain, SEOResult, DomainStatus

logger = logging.getLogger(__name__)


def generate_domains_csv(
    db: Session,
    tld: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50_000,
) -> tuple[str, str]:
    """
    Generate domains CSV export.
    Returns (csv_content, filename).
    """
    query = db.query(Domain)

    if tld:
        query = query.filter(Domain.tld == tld.lower().strip("."))
    if status:
        query = query.filter(Domain.check_status == status)
    if min_score is not None:
        query = query.filter(Domain.seo_score >= min_score)
    if max_score is not None:
        query = query.filter(Domain.seo_score <= max_score)
    if date_from:
        query = query.filter(Domain.fetched_date >= date_from)
    if date_to:
        query = query.filter(Domain.fetched_date <= date_to)

    domains = query.order_by(Domain.fetched_date.desc()).limit(limit).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "domain", "tld", "registrar", "seo_score", "status",
        "fetched_date", "registered_at"
    ])

    for d in domains:
        writer.writerow([
            d.name,
            d.tld,
            d.registrar or "",
            round(d.seo_score, 1) if d.seo_score is not None else "",
            d.check_status,
            d.fetched_date.strftime("%Y-%m-%d") if d.fetched_date else "",
            d.registered_at.strftime("%Y-%m-%d") if d.registered_at else "",
        ])

    filename = f"domains_{tld or 'all'}_{date.today()}.csv"
    return output.getvalue(), filename


def generate_seo_audit_csv(
    db: Session,
    domain_ids: Optional[list[int]] = None,
    min_score: Optional[float] = None,
    limit: int = 10_000,
) -> tuple[str, str]:
    """
    Generate full SEO audit CSV — one row per domain with all check scores.
    Returns (csv_content, filename).
    """
    # Get latest SEO result per domain
    subq = (
        db.query(
            SEOResult.domain_id,
            func.max(SEOResult.checked_at).label("max_checked")
        )
        .group_by(SEOResult.domain_id)
        .subquery()
    )

    query = (
        db.query(SEOResult, Domain)
        .join(subq, (SEOResult.domain_id == subq.c.domain_id) & (SEOResult.checked_at == subq.c.max_checked))
        .join(Domain, SEOResult.domain_id == Domain.id)
    )

    if domain_ids:
        query = query.filter(Domain.id.in_(domain_ids))
    if min_score is not None:
        query = query.filter(SEOResult.overall_score >= min_score)

    rows = query.order_by(SEOResult.overall_score.desc().nullslast()).limit(limit).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "domain", "tld", "overall_score", "checked_at",
        "dns_score", "https_score", "meta_score", "robots_score",
        "sitemap_score", "ssl_score", "speed_score", "mobile_score",
        "social_meta_score", "heading_score",
    ])

    for result, domain in rows:
        writer.writerow([
            domain.name,
            domain.tld,
            round(result.overall_score, 1) if result.overall_score is not None else "",
            result.checked_at.strftime("%Y-%m-%d %H:%M") if result.checked_at else "",
            result.dns_score or "",
            result.https_score or "",
            result.meta_score or "",
            result.robots_score or "",
            result.sitemap_score or "",
            result.ssl_score or "",
            result.speed_score or "",
            result.mobile_score or "",
            result.social_meta_score or "",
            result.heading_score or "",
        ])

    filename = f"seo_audit_{date.today()}.csv"
    return output.getvalue(), filename


def generate_summary_stats(db: Session) -> dict:
    """Generate stats dict for digest emails and summary reports."""
    from app.services.dashboard_service import get_user_stats
    stats = get_user_stats(db)
    stats["date"] = date.today().strftime("%B %d, %Y")
    return stats
