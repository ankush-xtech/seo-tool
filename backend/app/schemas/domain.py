from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.models.models import DomainStatus


class DomainBase(BaseModel):
    name: str
    tld: str
    registrar: Optional[str] = None
    registered_at: Optional[datetime] = None


class DomainPublic(DomainBase):
    id: int
    check_status: DomainStatus
    seo_score: Optional[float] = None
    fetched_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class DomainList(BaseModel):
    domains: list[DomainPublic]
    total: int
    page: int
    per_page: int


class DomainFilter(BaseModel):
    tld: Optional[str] = None
    status: Optional[DomainStatus] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    search: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class FetchTriggerRequest(BaseModel):
    fetch_date: Optional[str] = None   # YYYY-MM-DD, defaults to today

    @field_validator("fetch_date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("fetch_date must be YYYY-MM-DD format")
        return v


class FetchRunResponse(BaseModel):
    status: str
    date: str
    total_fetched: int
    new_domains: int
    duplicates_skipped: int
    duration_seconds: float
    task_id: Optional[str] = None


class FetchStatusResponse(BaseModel):
    task_id: str
    status: str          # PENDING | STARTED | SUCCESS | FAILURE | RETRY
    result: Optional[dict] = None
    error: Optional[str] = None


class DomainStatsResponse(BaseModel):
    total_domains: int
    fetched_today: int
    pending_check: int
    checked: int
    avg_seo_score: Optional[float] = None
