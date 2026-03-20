from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import User, AuditLog, AuditAction
from app.services.report_service import (
    generate_domains_csv, generate_seo_audit_csv, generate_summary_stats
)

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])


@router.get("/domains/csv")
def export_domains_csv(
    tld: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export filtered domain list as CSV."""
    content, filename = generate_domains_csv(
        db, tld=tld, status=status,
        min_score=min_score, max_score=max_score,
        date_from=date_from, date_to=date_to,
    )

    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.export,
        description=f"CSV export: domains (tld={tld}, status={status})",
    ))
    db.commit()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/seo-audit/csv")
def export_seo_audit_csv(
    min_score: Optional[float] = Query(None, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export full SEO audit results as CSV."""
    content, filename = generate_seo_audit_csv(db, min_score=min_score)

    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.export,
        description=f"CSV export: SEO audit (min_score={min_score})",
    ))
    db.commit()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/digest/send", dependencies=[Depends(require_admin)])
def send_digest_now(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: manually trigger digest email to self."""
    from app.services.notification_service import send_digest_email
    stats = generate_summary_stats(db)
    sent = send_digest_email(admin.email, admin.full_name, stats)
    return {
        "message": "Digest email sent" if sent else "SMTP not configured — digest not sent",
        "sent": sent,
    }


@router.get("/summary")
def get_summary_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get current summary stats (used by report builder UI)."""
    return generate_summary_stats(db)
