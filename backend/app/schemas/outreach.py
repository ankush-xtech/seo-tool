from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LeadPublic(BaseModel):
    """Single lead row for the outreach dashboard."""
    listing_id: int
    business_name: str
    website: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    # SEO
    seo_score: Optional[int] = None
    seo_verdict: Optional[str] = None
    seo_status: Optional[str] = None
    # Email outreach
    email_status: Optional[str] = None  # draft/sent/opened/clicked/replied
    email_sent_at: Optional[datetime] = None
    email_opened_at: Optional[datetime] = None
    email_clicked_at: Optional[datetime] = None
    email_replied_at: Optional[datetime] = None
    preview_url: Optional[str] = None


class LeadList(BaseModel):
    items: list[LeadPublic]
    total: int
    page: int
    per_page: int


class OutreachStats(BaseModel):
    total_leads: int = 0
    with_website: int = 0
    with_email: int = 0
    seo_checked: int = 0
    score_below_70: int = 0
    emails_sent: int = 0
    emails_opened: int = 0
    emails_clicked: int = 0
    emails_replied: int = 0
    open_rate: float = 0.0
    reply_rate: float = 0.0


class SendEmailsRequest(BaseModel):
    max_score: int = 70
    search_query_id: Optional[int] = None
    category: Optional[str] = None
    city: Optional[str] = None
    limit: int = 50


class EmailPreview(BaseModel):
    listing_id: int
    business_name: str
    to_email: str
    subject: str
    body_html: str
    seo_score: int
    problems: list[str]


class SendSelectedEmailsRequest(BaseModel):
    listing_ids: list[int]
    mode: str = "ai"  # "ai" or "template"
    with_preview: bool = False  # generate + deploy preview website to Vercel
    custom_prompt: Optional[str] = None  # override the default website generation prompt
    hero_image_url: Optional[str] = None  # custom hero banner image URL
    about_image_url: Optional[str] = None  # custom about section image URL
