from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DashboardStats(BaseModel):
    total_domains: int
    fetched_today: int
    pending_check: int
    checked: int
    failed: int
    avg_seo_score: Optional[float] = None
    score_distribution: dict  # {"good": N, "average": N, "poor": N}
    top_tlds: List[dict]      # [{"tld": "com", "count": N}]
    daily_fetched: List[dict] # [{"date": "2024-01-01", "count": N}]


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    admin_count: int
    total_domains: int
    fetched_today: int
    checked_today: int
    failed_today: int
    avg_seo_score: Optional[float] = None
    score_distribution: dict
    top_tlds: List[dict]
    daily_fetched: List[dict]
    recent_audit_logs: List[dict]


class AuditLogPublic(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    description: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogList(BaseModel):
    logs: List[AuditLogPublic]
    total: int
    page: int
    per_page: int
