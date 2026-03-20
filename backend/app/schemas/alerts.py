from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from app.models.models import AlertCondition, NotificationStatus


# ─── Alert Rules ──────────────────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    name: str
    condition: AlertCondition
    threshold: Optional[float] = None
    tld_filter: Optional[str] = None
    is_active: bool = True
    email_notify: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Rule name cannot be empty")
        return v.strip()

    @field_validator("threshold")
    @classmethod
    def threshold_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 <= v <= 100):
            raise ValueError("Threshold must be between 0 and 100")
        return v


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    condition: Optional[AlertCondition] = None
    threshold: Optional[float] = None
    tld_filter: Optional[str] = None
    is_active: Optional[bool] = None
    email_notify: Optional[bool] = None


class AlertRulePublic(BaseModel):
    id: int
    user_id: int
    name: str
    condition: AlertCondition
    threshold: Optional[float] = None
    tld_filter: Optional[str] = None
    is_active: bool
    email_notify: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Notifications ────────────────────────────────────────────────────────────

class NotificationPublic(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    status: NotificationStatus
    meta: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationList(BaseModel):
    notifications: List[NotificationPublic]
    total: int
    unread_count: int
    page: int
    per_page: int
