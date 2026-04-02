"""
Competitor Finder + Comparison
Discovers competitors for a target domain, runs SEO checks, fetches Semrush
metrics, and generates actionable insights.
"""

import io
import csv
import logging
import threading

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import (
    CompetitorAnalysis, CompetitorAnalysisStatus, Competitor,
    CompetitorInsight, AuditLog, AuditAction, User, BusinessListing,
)
from app.schemas.competitors import (
    CompetitorAnalysisCreate, CompetitorAnalysisPublic, CompetitorAnalysisDetail,
    CompetitorAnalysisList, CompetitorPublic, InsightPublic, ComparisonResponse,
)
from app.services.competitor_service import run_competitor_analysis, get_progress

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/competitors", tags=["Competitor Analysis"])


# ─── Start analysis ─────────────────────────────────────────────────────────

@router.post("/analyze")
def start_analysis(
    data: CompetitorAnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a competitor analysis for a target domain."""
    progress = get_progress()
    if progress["running"]:
        raise HTTPException(409, "A competitor analysis is already running. Please wait.")

    # Create analysis record
    analysis = CompetitorAnalysis(
        user_id=current_user.id,
        business_listing_id=data.business_listing_id,
        target_domain=data.target_domain,
        target_category=data.category,
        target_city=data.city,
        target_state=data.state,
        status=CompetitorAnalysisStatus.pending,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.competitor_analysis,
        description=f"Started competitor analysis for {data.target_domain}",
    ))
    db.commit()

    # Spawn background thread
    thread = threading.Thread(
        target=run_competitor_analysis,
        args=(analysis.id,),
        kwargs={
            "include_seo": data.include_seo_checks,
            "include_semrush": data.include_semrush,
            "max_competitors": data.max_competitors,
        },
        daemon=True,
    )
    thread.start()

    return {
        "status": "started",
        "analysis_id": analysis.id,
        "target_domain": data.target_domain,
    }


# ─── Progress polling ────────────────────────────────────────────────────────

@router.get("/progress")
def get_analysis_progress(current_user: User = Depends(get_current_user)):
    """Get real-time progress of the current competitor analysis."""
    return get_progress()


# ─── List past analyses ──────────────────────────────────────────────────────

@router.get("/analyses", response_model=CompetitorAnalysisList)
def list_analyses(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List past competitor analyses."""
    q = db.query(CompetitorAnalysis).filter(
        CompetitorAnalysis.user_id == current_user.id
    )
    if status:
        q = q.filter(CompetitorAnalysis.status == status)

    total = q.count()
    items = q.order_by(CompetitorAnalysis.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return CompetitorAnalysisList(
        items=[CompetitorAnalysisPublic.model_validate(i) for i in items],
        total=total, page=page, per_page=per_page,
    )


# ─── Get analysis detail ────────────────────────────────────────────────────

@router.get("/analyses/{analysis_id}", response_model=CompetitorAnalysisDetail)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single analysis with competitors and insights."""
    analysis = db.query(CompetitorAnalysis).filter(
        CompetitorAnalysis.id == analysis_id,
    ).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    return CompetitorAnalysisDetail(
        **CompetitorAnalysisPublic.model_validate(analysis).model_dump(),
        competitors=[CompetitorPublic.model_validate(c) for c in analysis.competitors],
        insights=[InsightPublic.model_validate(i) for i in analysis.insights],
    )


# ─── Comparison data (structured for charts) ────────────────────────────────

@router.get("/analyses/{analysis_id}/comparison", response_model=ComparisonResponse)
def get_comparison(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get structured comparison data for charts and tables."""
    analysis = db.query(CompetitorAnalysis).filter(
        CompetitorAnalysis.id == analysis_id,
    ).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    target = None
    competitors = []
    for comp in analysis.competitors:
        pub = CompetitorPublic.model_validate(comp)
        if comp.is_target:
            target = pub
        else:
            competitors.append(pub)

    # Sort competitors by SEO score descending
    competitors.sort(key=lambda c: c.seo_overall_score or 0, reverse=True)

    return ComparisonResponse(
        target=target,
        competitors=competitors,
        insights=[InsightPublic.model_validate(i) for i in analysis.insights],
    )


# ─── Export CSV ──────────────────────────────────────────────────────────────

@router.get("/analyses/{analysis_id}/export/csv")
def export_analysis_csv(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export competitor comparison as CSV."""
    analysis = db.query(CompetitorAnalysis).filter(
        CompetitorAnalysis.id == analysis_id,
    ).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Domain", "Business Name", "Is Target", "Source", "Search Rank",
        "SEO Score", "DNS", "HTTPS", "Meta", "Robots", "Sitemap",
        "SSL", "Speed", "Mobile", "Social Meta", "Headings",
        "Organic Traffic", "Organic Keywords", "Domain Authority",
        "Backlinks", "Referring Domains", "Maps Rating", "Maps Reviews",
    ])

    for c in analysis.competitors:
        writer.writerow([
            c.domain, c.business_name, "Yes" if c.is_target else "No",
            c.discovery_source, c.search_rank,
            c.seo_overall_score, c.seo_dns_score, c.seo_https_score,
            c.seo_meta_score, c.seo_robots_score, c.seo_sitemap_score,
            c.seo_ssl_score, c.seo_speed_score, c.seo_mobile_score,
            c.seo_social_meta_score, c.seo_heading_score,
            c.organic_traffic, c.organic_keywords, c.domain_authority,
            c.backlinks_total, c.referring_domains,
            c.maps_rating, c.maps_reviews,
        ])

    output.seek(0)

    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.export,
        description=f"Exported competitor analysis #{analysis_id} as CSV",
    ))
    db.commit()

    filename = f"competitor_analysis_{analysis.target_domain}.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─── Delete analysis ─────────────────────────────────────────────────────────

@router.delete("/analyses/{analysis_id}")
def delete_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a competitor analysis. Admin only."""
    analysis = db.query(CompetitorAnalysis).filter(
        CompetitorAnalysis.id == analysis_id,
    ).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    db.delete(analysis)
    db.commit()
    return {"status": "deleted", "analysis_id": analysis_id}


# ─── Get business listings with websites (for frontend dropdown) ────────────

@router.get("/listings-with-websites")
def get_listings_with_websites(
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get business listings that have websites (for the analysis launcher dropdown)."""
    q = db.query(BusinessListing).filter(
        BusinessListing.website.isnot(None),
        BusinessListing.website != "",
    )
    if search:
        q = q.filter(BusinessListing.business_name.ilike(f"%{search}%"))

    listings = q.order_by(BusinessListing.id.desc()).limit(limit).all()

    return [
        {
            "id": l.id,
            "business_name": l.business_name,
            "website": l.website,
            "category": l.category,
            "city": l.city,
            "state": l.state,
            "rating": l.rating,
            "reviews_count": l.reviews_count,
        }
        for l in listings
    ]
