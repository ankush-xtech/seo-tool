from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Enum, Float, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.session import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class DomainStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    fetch_domains = "fetch_domains"
    run_seo_check = "run_seo_check"
    export = "export"
    user_created = "user_created"
    user_updated = "user_updated"
    user_deleted = "user_deleted"
    settings_updated = "settings_updated"
    maps_search = "maps_search"
    outreach_seo_check = "outreach_seo_check"
    outreach_email_sent = "outreach_email_sent"


class AlertCondition(str, enum.Enum):
    score_above = "score_above"
    score_below = "score_below"
    score_drop = "score_drop"
    check_failed = "check_failed"


class NotificationStatus(str, enum.Enum):
    unread = "unread"
    read = "read"


class MapSearchStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class OutreachEmailStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    opened = "opened"
    clicked = "clicked"
    replied = "replied"
    bounced = "bounced"


class SEOCheckStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(191), unique=True, index=True, nullable=False)
    full_name = Column(String(191), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    watchlist = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    alert_rules = relationship("AlertRule", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email} [{self.role}]>"


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), unique=True, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="refresh_tokens")


class Domain(Base):
    __tablename__ = "domains"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(191), unique=True, index=True, nullable=False)
    tld = Column(String(50), index=True, nullable=False)
    registrar = Column(String(191), nullable=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)
    fetched_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    check_status = Column(Enum(DomainStatus), default=DomainStatus.pending, index=True)
    seo_score = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    seo_results = relationship("SEOResult", back_populates="domain", cascade="all, delete-orphan")
    watchlist = relationship("Watchlist", back_populates="domain")
    __table_args__ = (
        Index("ix_domain_tld_date", "tld", "fetched_date"),
        Index("ix_domain_status_score", "check_status", "seo_score"),
    )

    def __repr__(self):
        return f"<Domain {self.name} score={self.seo_score}>"


class SEOResult(Base):
    __tablename__ = "seo_results"
    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    dns_score = Column(Float, nullable=True)
    https_score = Column(Float, nullable=True)
    meta_score = Column(Float, nullable=True)
    robots_score = Column(Float, nullable=True)
    sitemap_score = Column(Float, nullable=True)
    speed_score = Column(Float, nullable=True)
    mobile_score = Column(Float, nullable=True)
    ssl_score = Column(Float, nullable=True)
    social_meta_score = Column(Float, nullable=True)
    heading_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    dns_data = Column(JSON, nullable=True)
    https_data = Column(JSON, nullable=True)
    meta_data = Column(JSON, nullable=True)
    robots_data = Column(JSON, nullable=True)
    sitemap_data = Column(JSON, nullable=True)
    speed_data = Column(JSON, nullable=True)
    ssl_data = Column(JSON, nullable=True)
    social_meta_data = Column(JSON, nullable=True)
    heading_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    domain = relationship("Domain", back_populates="seo_results")


class Watchlist(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False)
    alert_on_score_change = Column(Boolean, default=False)
    score_threshold = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="watchlist")
    domain = relationship("Domain", back_populates="watchlist")
    __table_args__ = (
        Index("ix_watchlist_user_domain", "user_id", "domain_id", unique=True),
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(191), nullable=False)
    condition = Column(Enum(AlertCondition), nullable=False)
    threshold = Column(Float, nullable=True)
    tld_filter = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    email_notify = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user = relationship("User", back_populates="alert_rules")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.unread, index=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(Enum(AuditAction), nullable=False, index=True)
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user = relationship("User", back_populates="audit_logs")


class MapSearchQuery(Base):
    __tablename__ = "map_search_queries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    query_text = Column(String(500), nullable=False)
    category = Column(String(191), nullable=True, index=True)
    city = Column(String(191), nullable=True, index=True)
    state = Column(String(50), nullable=True)
    status = Column(Enum(MapSearchStatus), default=MapSearchStatus.pending, index=True)
    results_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    provider = Column(String(50), default="serpapi")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    listings = relationship("BusinessListing", back_populates="search_query", cascade="all, delete-orphan")
    user = relationship("User")
    __table_args__ = (
        Index("ix_map_search_category_city", "category", "city"),
    )


class BusinessListing(Base):
    __tablename__ = "business_listings"
    id = Column(Integer, primary_key=True, index=True)
    search_query_id = Column(Integer, ForeignKey("map_search_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id = Column(String(255), nullable=True, index=True)
    business_name = Column(String(500), nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(191), nullable=True, index=True)
    state = Column(String(50), nullable=True)
    postcode = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(500), nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, nullable=True)
    category = Column(String(255), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    search_query = relationship("MapSearchQuery", back_populates="listings")
    seo_check = relationship("ListingSEOCheck", back_populates="listing", uselist=False, cascade="all, delete-orphan")
    outreach_emails = relationship("OutreachEmail", back_populates="listing", cascade="all, delete-orphan")
    __table_args__ = (
        Index("ix_listing_name_city", "business_name", "city"),
    )


class ListingSEOCheck(Base):
    __tablename__ = "listing_seo_checks"
    id = Column(Integer, primary_key=True, index=True)
    business_listing_id = Column(Integer, ForeignKey("business_listings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    overall_score = Column(Integer, default=0)
    verdict = Column(String(50), default="Pending")
    # Technical checks
    check_ssl = Column(String(10), default="pending")
    check_robots = Column(String(10), default="pending")
    check_sitemap = Column(String(10), default="pending")
    check_canonical = Column(String(10), default="pending")
    check_mobile = Column(String(10), default="pending")
    check_speed = Column(String(10), default="pending")
    load_time = Column(Float, nullable=True)
    # On-page checks
    check_h1 = Column(String(10), default="pending")
    check_title = Column(String(10), default="pending")
    title_text = Column(String(255), nullable=True)
    title_length = Column(Integer, nullable=True)
    check_description = Column(String(10), default="pending")
    description_text = Column(String(500), nullable=True)
    description_length = Column(Integer, nullable=True)
    check_alt_tags = Column(String(10), default="pending")
    images_total = Column(Integer, default=0)
    images_missing_alt = Column(Integer, default=0)
    # Local SEO checks
    check_business_name = Column(String(10), default="pending")
    check_phone = Column(String(10), default="pending")
    check_local_schema = Column(String(10), default="pending")
    check_social_links = Column(String(10), default="pending")
    check_contact_page = Column(String(10), default="pending")
    # Meta
    status = Column(Enum(SEOCheckStatus), default=SEOCheckStatus.pending, index=True)
    error_message = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    listing = relationship("BusinessListing", back_populates="seo_check")


class OutreachEmail(Base):
    __tablename__ = "outreach_emails"
    id = Column(Integer, primary_key=True, index=True)
    business_listing_id = Column(Integer, ForeignKey("business_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    seo_check_id = Column(Integer, ForeignKey("listing_seo_checks.id", ondelete="SET NULL"), nullable=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    status = Column(Enum(OutreachEmailStatus), default=OutreachEmailStatus.draft, index=True)
    sendgrid_message_id = Column(String(255), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    preview_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    listing = relationship("BusinessListing", back_populates="outreach_emails")
    seo_check = relationship("ListingSEOCheck")
