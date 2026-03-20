from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import User
from app.services.dashboard_service import get_admin_stats, get_user_stats, get_audit_logs

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/admin")
def admin_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Full admin dashboard stats."""
    return get_admin_stats(db)


@router.get("/user")
def user_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """User dashboard stats."""
    return get_user_stats(db)


@router.get("/audit-logs")
def audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: paginated audit log viewer."""
    return get_audit_logs(db, page=page, per_page=per_page, action=action, user_id=user_id)
