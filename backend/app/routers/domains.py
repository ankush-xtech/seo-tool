from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import Domain, DomainStatus, User
from app.schemas.domain import (
    DomainPublic, DomainList, FetchTriggerRequest,
    FetchRunResponse, FetchStatusResponse, DomainStatsResponse
)
from app.services.domain_storage import get_domain_stats

router = APIRouter(prefix="/domains", tags=["Domains"])


# ─── List & Search ─────────────────────────────────────────────────────────────

@router.get("/", response_model=DomainList)
def list_domains(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    tld: Optional[str] = None,
    status: Optional[DomainStatus] = None,
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_by: str = Query("fetched_date", regex="^(fetched_date|seo_score|name)$"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List domains with filters, pagination, and sorting."""
    query = db.query(Domain)

    if tld:
        query = query.filter(Domain.tld == tld.lower().strip("."))
    if status:
        query = query.filter(Domain.check_status == status)
    if min_score is not None:
        query = query.filter(Domain.seo_score >= min_score)
    if max_score is not None:
        query = query.filter(Domain.seo_score <= max_score)
    if search:
        query = query.filter(Domain.name.contains(search.lower()))
    if date_from:
        query = query.filter(Domain.fetched_date >= date_from)
    if date_to:
        query = query.filter(Domain.fetched_date <= date_to)

    # Sorting
    sort_col = {
        "fetched_date": Domain.fetched_date,
        "seo_score": Domain.seo_score,
        "name": Domain.name,
    }.get(sort_by, Domain.fetched_date)

    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc().nullslast())

    total = query.count()
    domains = query.offset((page - 1) * per_page).limit(per_page).all()

    return {"domains": domains, "total": total, "page": page, "per_page": per_page}


@router.get("/stats", response_model=DomainStatsResponse)
def domain_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Returns aggregate domain stats for the dashboard."""
    return get_domain_stats(db)


@router.get("/{domain_id}", response_model=DomainPublic)
def get_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a single domain by ID."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


# ─── Admin: Manual Fetch Trigger ──────────────────────────────────────────────

@router.post("/fetch", response_model=FetchRunResponse, dependencies=[Depends(require_admin)])
def trigger_fetch(
    data: FetchTriggerRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Admin: manually trigger a domain fetch run.
    Dispatches a Celery task and returns the task ID for polling.
    """
    from app.tasks.domain_tasks import fetch_and_store_domains

    task = fetch_and_store_domains.apply_async(
        kwargs={
            "fetch_date_str": data.fetch_date,
            "triggered_by_user_id": admin.id,
        }
    )

    return FetchRunResponse(
        status="queued",
        date=data.fetch_date or "today",
        total_fetched=0,
        new_domains=0,
        duplicates_skipped=0,
        duration_seconds=0.0,
        task_id=task.id,
    )


@router.get("/fetch/status/{task_id}", response_model=FetchStatusResponse)
def get_fetch_status(
    task_id: str,
    _: User = Depends(require_admin),
):
    """Admin: poll the status of a running fetch task."""
    from app.tasks.celery_app import celery_app
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)

    return FetchStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result if result.successful() else None,
        error=str(result.result) if result.failed() else None,
    )


# ─── Export ───────────────────────────────────────────────────────────────────

@router.get("/export/csv")
def export_domains_csv(
    tld: Optional[str] = None,
    status: Optional[DomainStatus] = None,
    min_score: Optional[float] = Query(None, ge=0, le=100),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export filtered domains as CSV download."""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from app.models.models import AuditLog, AuditAction

    query = db.query(Domain)
    if tld:
        query = query.filter(Domain.tld == tld.lower().strip("."))
    if status:
        query = query.filter(Domain.check_status == status)
    if min_score is not None:
        query = query.filter(Domain.seo_score >= min_score)
    if date_from:
        query = query.filter(Domain.fetched_date >= date_from)
    if date_to:
        query = query.filter(Domain.fetched_date <= date_to)

    domains = query.order_by(Domain.fetched_date.desc()).limit(50_000).all()

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["domain", "tld", "registrar", "seo_score", "status", "fetched_date", "registered_at"])
    for d in domains:
        writer.writerow([
            d.name, d.tld, d.registrar or "",
            d.seo_score or "", d.check_status,
            d.fetched_date.strftime("%Y-%m-%d") if d.fetched_date else "",
            d.registered_at.strftime("%Y-%m-%d") if d.registered_at else "",
        ])

    # Audit
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.export,
        description=f"CSV export: {len(domains)} domains",
        meta={"count": len(domains), "filters": {"tld": tld, "status": str(status)}},
    ))
    db.commit()

    output.seek(0)
    filename = f"domains_{tld or 'all'}_{date_from.date() if date_from else 'all'}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
