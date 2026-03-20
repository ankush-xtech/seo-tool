"""
SEO Results Router
==================
Endpoints for triggering SEO checks and retrieving results.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import Domain, SEOResult, DomainStatus, User
from app.schemas.seo import (
    SEOResultPublic, SEOCheckRequest, SEOCheckResponse,
    DomainDetailResponse
)

router = APIRouter(prefix="/seo", tags=["SEO Checks"])


@router.post("/check", response_model=SEOCheckResponse)
async def check_domain_now(
    data: SEOCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run SEO check on a domain RIGHT NOW (synchronous — waits for result).
    No Redis/Celery needed. Results returned immediately.
    Use for single domain checks from the UI.
    """
    from app.services.seo_engine import run_all_checks

    domain_name = data.domain.lower().strip().rstrip("/")
    # Strip protocol if pasted
    for prefix in ("https://", "http://", "www."):
        if domain_name.startswith(prefix):
            domain_name = domain_name[len(prefix):]

    # Run checks
    try:
        results = await run_all_checks(domain_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SEO check failed: {str(e)}")

    overall_score = results.get("overall_score", 0)

    # Save to DB — create domain if it doesn't exist
    domain = db.query(Domain).filter(Domain.name == domain_name).first()
    if not domain:
        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        domain = Domain(
            name=domain_name,
            tld=tld,
            check_status=DomainStatus.done,
            seo_score=overall_score,
        )
        db.add(domain)
        db.commit()
        db.refresh(domain)
    else:
        domain.seo_score = overall_score
        domain.check_status = DomainStatus.done

    seo_result = SEOResult(
        domain_id=domain.id,
        overall_score=overall_score,
        dns_score=results["dns"].get("score"),
        https_score=results["https"].get("score"),
        meta_score=results["meta"].get("score"),
        robots_score=results["robots"].get("score"),
        sitemap_score=results["sitemap"].get("score"),
        ssl_score=results["ssl"].get("score"),
        speed_score=results["speed"].get("score"),
        mobile_score=results["mobile"].get("score"),
        social_meta_score=results["social_meta"].get("score"),
        heading_score=results["headings"].get("score"),
        dns_data=results.get("dns"),
        https_data=results.get("https"),
        meta_data=results.get("meta"),
        robots_data=results.get("robots"),
        sitemap_data=results.get("sitemap"),
        speed_data=results.get("speed"),
        ssl_data=results.get("ssl"),
        social_meta_data=results.get("social_meta"),
        heading_data=results.get("headings"),
    )
    db.add(seo_result)
    db.commit()
    db.refresh(seo_result)

    return SEOCheckResponse(
        domain=domain_name,
        overall_score=overall_score,
        result_id=seo_result.id,
        checks=results,
    )


@router.get("/results/{domain_id}", response_model=list[SEOResultPublic])
def get_domain_results(
    domain_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get all SEO check history for a domain (latest first)."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    results = (
        db.query(SEOResult)
        .filter(SEOResult.domain_id == domain_id)
        .order_by(SEOResult.checked_at.desc())
        .limit(limit)
        .all()
    )
    return results


@router.get("/detail/{result_id}", response_model=SEOResultPublic)
def get_result_detail(
    result_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get full detail of a single SEO check result including raw data."""
    result = db.query(SEOResult).filter(SEOResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@router.get("/domain/{domain_name:path}", response_model=DomainDetailResponse)
def get_domain_by_name(
    domain_name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get domain + latest SEO result by domain name."""
    domain = db.query(Domain).filter(Domain.name == domain_name.lower()).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    latest = (
        db.query(SEOResult)
        .filter(SEOResult.domain_id == domain.id)
        .order_by(SEOResult.checked_at.desc())
        .first()
    )

    return DomainDetailResponse(domain=domain, latest_result=latest)
