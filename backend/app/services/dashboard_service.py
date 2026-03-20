"""
Dashboard Service
=================
Aggregates stats for admin and user dashboards.
"""

from datetime import date, datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date

from app.models.models import (
    Domain, DomainStatus, SEOResult, User, UserRole,
    AuditLog, AuditAction
)


def get_admin_stats(db: Session) -> dict:
    """Full stats for the admin dashboard."""

    # ── User stats ────────────────────────────────────────────────────────────
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    admin_count = db.query(func.count(User.id)).filter(User.role == UserRole.admin).scalar() or 0

    # ── Domain stats ──────────────────────────────────────────────────────────
    total_domains = db.query(func.count(Domain.id)).scalar() or 0
    today = date.today()

    fetched_today = db.query(func.count(Domain.id)).filter(
        func.date(Domain.fetched_date) == today
    ).scalar() or 0

    checked_today = db.query(func.count(Domain.id)).filter(
        func.date(Domain.updated_at) == today,
        Domain.check_status == DomainStatus.done
    ).scalar() or 0

    failed_today = db.query(func.count(Domain.id)).filter(
        func.date(Domain.updated_at) == today,
        Domain.check_status == DomainStatus.failed
    ).scalar() or 0

    pending = db.query(func.count(Domain.id)).filter(
        Domain.check_status == DomainStatus.pending
    ).scalar() or 0

    avg_score = db.query(func.avg(Domain.seo_score)).filter(
        Domain.seo_score.isnot(None)
    ).scalar()

    # ── Score distribution ────────────────────────────────────────────────────
    good = db.query(func.count(Domain.id)).filter(Domain.seo_score >= 70).scalar() or 0
    average = db.query(func.count(Domain.id)).filter(
        Domain.seo_score >= 40, Domain.seo_score < 70
    ).scalar() or 0
    poor = db.query(func.count(Domain.id)).filter(
        Domain.seo_score.isnot(None), Domain.seo_score < 40
    ).scalar() or 0

    # ── Top TLDs ──────────────────────────────────────────────────────────────
    top_tlds_rows = (
        db.query(Domain.tld, func.count(Domain.id).label("count"))
        .group_by(Domain.tld)
        .order_by(func.count(Domain.id).desc())
        .limit(8)
        .all()
    )
    top_tlds = [{"tld": r.tld, "count": r.count} for r in top_tlds_rows]

    # ── Daily fetched (last 14 days) ──────────────────────────────────────────
    daily_fetched = _get_daily_fetched(db, days=14)

    # ── Recent audit logs ─────────────────────────────────────────────────────
    audit_rows = (
        db.query(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    recent_audit = [
        {
            "id": row.AuditLog.id,
            "action": row.AuditLog.action,
            "description": row.AuditLog.description,
            "user_email": row.email,
            "ip_address": row.AuditLog.ip_address,
            "created_at": row.AuditLog.created_at.isoformat() if row.AuditLog.created_at else None,
        }
        for row in audit_rows
    ]

    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_count": admin_count,
        "total_domains": total_domains,
        "fetched_today": fetched_today,
        "checked_today": checked_today,
        "failed_today": failed_today,
        "pending_check": pending,
        "avg_seo_score": round(float(avg_score), 1) if avg_score else None,
        "score_distribution": {"good": good, "average": average, "poor": poor},
        "top_tlds": top_tlds,
        "daily_fetched": daily_fetched,
        "recent_audit_logs": recent_audit,
    }


def get_user_stats(db: Session) -> dict:
    """Stats for the regular user dashboard."""
    today = date.today()

    total_domains = db.query(func.count(Domain.id)).scalar() or 0
    fetched_today = db.query(func.count(Domain.id)).filter(
        func.date(Domain.fetched_date) == today
    ).scalar() or 0
    pending = db.query(func.count(Domain.id)).filter(
        Domain.check_status == DomainStatus.pending
    ).scalar() or 0
    checked = db.query(func.count(Domain.id)).filter(
        Domain.check_status == DomainStatus.done
    ).scalar() or 0
    failed = db.query(func.count(Domain.id)).filter(
        Domain.check_status == DomainStatus.failed
    ).scalar() or 0

    avg_score = db.query(func.avg(Domain.seo_score)).filter(
        Domain.seo_score.isnot(None)
    ).scalar()

    good = db.query(func.count(Domain.id)).filter(Domain.seo_score >= 70).scalar() or 0
    average = db.query(func.count(Domain.id)).filter(
        Domain.seo_score >= 40, Domain.seo_score < 70
    ).scalar() or 0
    poor = db.query(func.count(Domain.id)).filter(
        Domain.seo_score.isnot(None), Domain.seo_score < 40
    ).scalar() or 0

    top_tlds_rows = (
        db.query(Domain.tld, func.count(Domain.id).label("count"))
        .group_by(Domain.tld)
        .order_by(func.count(Domain.id).desc())
        .limit(6)
        .all()
    )
    top_tlds = [{"tld": r.tld, "count": r.count} for r in top_tlds_rows]
    daily_fetched = _get_daily_fetched(db, days=7)

    return {
        "total_domains": total_domains,
        "fetched_today": fetched_today,
        "pending_check": pending,
        "checked": checked,
        "failed": failed,
        "avg_seo_score": round(float(avg_score), 1) if avg_score else None,
        "score_distribution": {"good": good, "average": average, "poor": poor},
        "top_tlds": top_tlds,
        "daily_fetched": daily_fetched,
    }


def get_audit_logs(db: Session, page: int = 1, per_page: int = 20,
                   action: str = None, user_id: int = None) -> dict:
    query = (
        db.query(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
    )
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    logs = [
        {
            "id": row.AuditLog.id,
            "user_id": row.AuditLog.user_id,
            "user_email": row.email,
            "action": row.AuditLog.action,
            "description": row.AuditLog.description,
            "ip_address": row.AuditLog.ip_address,
            "created_at": row.AuditLog.created_at.isoformat() if row.AuditLog.created_at else None,
        }
        for row in rows
    ]
    return {"logs": logs, "total": total, "page": page, "per_page": per_page}


def _get_daily_fetched(db: Session, days: int = 14) -> list:
    """Returns daily domain fetch counts for the last N days."""
    result = []
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        count = db.query(func.count(Domain.id)).filter(
            func.date(Domain.fetched_date) == d
        ).scalar() or 0
        result.append({"date": d.strftime("%b %d"), "count": count})
    return result
