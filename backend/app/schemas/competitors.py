from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class CompetitorAnalysisCreate(BaseModel):
    target_domain: str
    business_listing_id: Optional[int] = None
    category: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    max_competitors: int = 10
    include_seo_checks: bool = True
    include_semrush: bool = True

    @field_validator("max_competitors")
    @classmethod
    def validate_max(cls, v):
        if v < 1 or v > 20:
            raise ValueError("max_competitors must be between 1 and 20")
        return v

    @field_validator("target_domain")
    @classmethod
    def clean_domain(cls, v):
        v = v.strip().lower()
        for prefix in ("https://", "http://", "www."):
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v.rstrip("/")


class CompetitorPublic(BaseModel):
    id: int
    domain: str
    business_name: Optional[str] = None
    discovery_source: Optional[str] = None
    search_rank: Optional[int] = None
    is_target: bool = False

    # SEO scores
    seo_overall_score: Optional[float] = None
    seo_dns_score: Optional[float] = None
    seo_https_score: Optional[float] = None
    seo_meta_score: Optional[float] = None
    seo_robots_score: Optional[float] = None
    seo_sitemap_score: Optional[float] = None
    seo_speed_score: Optional[float] = None
    seo_mobile_score: Optional[float] = None
    seo_ssl_score: Optional[float] = None
    seo_social_meta_score: Optional[float] = None
    seo_heading_score: Optional[float] = None

    # Semrush metrics
    semrush_rank: Optional[int] = None
    organic_traffic: Optional[int] = None
    organic_keywords: Optional[int] = None
    domain_authority: Optional[float] = None
    backlinks_total: Optional[int] = None
    referring_domains: Optional[int] = None

    # Maps data
    maps_rating: Optional[float] = None
    maps_reviews: Optional[int] = None

    model_config = {"from_attributes": True}


class InsightPublic(BaseModel):
    id: int
    insight_type: str
    severity: str
    title: str
    description: str
    meta: Optional[dict] = None

    model_config = {"from_attributes": True}


class CompetitorAnalysisPublic(BaseModel):
    id: int
    target_domain: str
    target_category: Optional[str] = None
    target_city: Optional[str] = None
    target_state: Optional[str] = None
    status: str
    discovery_method: Optional[str] = None
    competitors_found: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CompetitorAnalysisDetail(CompetitorAnalysisPublic):
    competitors: list[CompetitorPublic] = []
    insights: list[InsightPublic] = []


class ComparisonResponse(BaseModel):
    target: Optional[CompetitorPublic] = None
    competitors: list[CompetitorPublic] = []
    insights: list[InsightPublic] = []


class CompetitorAnalysisList(BaseModel):
    items: list[CompetitorAnalysisPublic]
    total: int
    page: int
    per_page: int
