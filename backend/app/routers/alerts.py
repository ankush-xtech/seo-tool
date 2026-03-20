from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import AlertRule, User
from app.schemas.alerts import (
    AlertRuleCreate, AlertRuleUpdate, AlertRulePublic,
    NotificationPublic, NotificationList
)
from app.services.notification_service import (
    get_notifications, mark_read, get_unread_count, create_notification
)

router = APIRouter(prefix="/alerts", tags=["Alerts & Notifications"])


# ─── Alert Rules ──────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[AlertRulePublic])
def list_alert_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all alert rules for the current user."""
    return db.query(AlertRule).filter(AlertRule.user_id == current_user.id).all()


@router.post("/rules", response_model=AlertRulePublic, status_code=201)
def create_alert_rule(
    data: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new alert rule."""
    rule = AlertRule(user_id=current_user.id, **data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRulePublic)
def update_alert_rule(
    rule_id: int,
    data: AlertRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an alert rule."""
    rule = db.query(AlertRule).filter(
        AlertRule.id == rule_id,
        AlertRule.user_id == current_user.id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an alert rule."""
    rule = db.query(AlertRule).filter(
        AlertRule.id == rule_id,
        AlertRule.user_id == current_user.id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Alert rule deleted"}


# ─── Notifications ────────────────────────────────────────────────────────────

@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's notifications."""
    result = get_notifications(db, current_user.id, unread_only, page, per_page)
    return result


@router.get("/notifications/unread-count")
def unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fast endpoint to get unread count for the bell icon."""
    return {"count": get_unread_count(db, current_user.id)}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    mark_read(db, current_user.id, notification_id)
    return {"message": "Marked as read"}


@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read."""
    count = mark_read(db, current_user.id)
    return {"message": f"Marked {count} notifications as read"}


# ─── Admin: test notification ─────────────────────────────────────────────────

@router.post("/test", dependencies=[Depends(require_admin)])
def send_test_notification(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: send a test notification to yourself."""
    create_notification(
        db=db,
        user_id=current_user.id,
        title="Test notification",
        message="This is a test notification from the SEO Automation Tool.",
        meta={"type": "test"},
    )
    return {"message": "Test notification created"}
