from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
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


@router.get("/stats", response_model=DomainStatsResponse)
def domain_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return get_domain_stats(db)


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
    sort_by: str = Query("fetched_date"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
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

        sort_col = {
            "fetched_date": Domain.fetched_date,
            "seo_score":    Domain.seo_score,
            "name":         Domain.name,
        }.get(sort_by, Domain.fetched_date)

        if sort_dir == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        total = query.count()
        domains = query.offset((page - 1) * per_page).limit(per_page).all()

        return {"domains": domains, "total": total, "page": page, "per_page": per_page}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"list_domains error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["domain", "tld", "registrar", "seo_score", "status", "fetched_date"])
    for d in domains:
        writer.writerow([
            d.name, d.tld, d.registrar or "",
            d.seo_score or "", d.check_status,
            d.fetched_date.strftime("%Y-%m-%d") if d.fetched_date else "",
        ])

    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.export,
        description=f"CSV export: {len(domains)} domains",
    ))
    db.commit()

    output.seek(0)
    from datetime import date
    filename = f"domains_{date.today()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/fetch/status/{task_id}", response_model=FetchStatusResponse)
def get_fetch_status(task_id: str, _: User = Depends(require_admin)):
    try:
        from app.tasks.celery_app import celery_app
        from celery.result import AsyncResult
        result = AsyncResult(task_id, app=celery_app)
        return FetchStatusResponse(
            task_id=task_id,
            status=result.status,
            result=result.result if result.successful() else None,
            error=str(result.result) if result.failed() else None,
        )
    except Exception:
        return FetchStatusResponse(task_id=task_id, status="UNKNOWN")


@router.get("/{domain_id}", response_model=DomainPublic)
def get_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain
