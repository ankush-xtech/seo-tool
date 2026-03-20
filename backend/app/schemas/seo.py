from pydantic import BaseModel, field_validator
from typing import Optional, Any
from datetime import datetime


class SEOCheckRequest(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        v = v.lower().strip().rstrip("/")
        for prefix in ("https://", "http://", "www."):
            if v.startswith(prefix):
                v = v[len(prefix):]
        if not v or "." not in v:
            raise ValueError("Invalid domain name")
        return v


class SEOCheckResponse(BaseModel):
    domain: str
    overall_score: float
    result_id: int
    checks: dict[str, Any]


class SEOResultPublic(BaseModel):
    id: int
    domain_id: int
    checked_at: datetime
    overall_score: Optional[float] = None

    # Scores
    dns_score: Optional[float] = None
    https_score: Optional[float] = None
    meta_score: Optional[float] = None
    robots_score: Optional[float] = None
    sitemap_score: Optional[float] = None
    ssl_score: Optional[float] = None
    speed_score: Optional[float] = None
    mobile_score: Optional[float] = None
    social_meta_score: Optional[float] = None
    heading_score: Optional[float] = None

    # Raw data
    dns_data: Optional[dict] = None
    https_data: Optional[dict] = None
    meta_data: Optional[dict] = None
    robots_data: Optional[dict] = None
    sitemap_data: Optional[dict] = None
    speed_data: Optional[dict] = None
    ssl_data: Optional[dict] = None
    social_meta_data: Optional[dict] = None
    heading_data: Optional[dict] = None

    model_config = {"from_attributes": True}


class DomainDetailResponse(BaseModel):
    domain: Any         # DomainPublic
    latest_result: Optional[SEOResultPublic] = None

    model_config = {"from_attributes": True}
