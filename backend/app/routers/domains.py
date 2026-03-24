from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import csv
import io
import re

from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import Domain, DomainStatus, User, AuditLog, AuditAction
from app.schemas.domain import (
    DomainPublic, DomainList, FetchTriggerRequest,
    FetchRunResponse, FetchStatusResponse, DomainStatsResponse, DomainImportResponse
)
from app.services.domain_storage import get_domain_stats

router = APIRouter(prefix="/domains", tags=["Domains"])

DOMAIN_REGEX = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def normalize_domain(raw: str) -> str:
    value = (raw or "").strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/")[0].split(":")[0].strip()
    if value.startswith("www."):
        value = value[4:]
    return value


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
            query = query.order_by(sort_col.asc(), Domain.id.asc())
        else:
            query = query.order_by(sort_col.desc(), Domain.id.desc())

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
    limit: int = Query(2000, ge=1, le=2000),
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

    domains = query.order_by(Domain.fetched_date.desc(), Domain.id.desc()).limit(limit).all()

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


@router.post("/import/csv", response_model=DomainImportResponse)
async def import_domains_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig", errors="ignore")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read CSV file")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    report_rows = []
    domains_to_insert = []
    seen = set()
    total_rows = 0
    invalid_count = 0

    for idx, row in enumerate(rows):
        if not row or not any(cell.strip() for cell in row):
            continue

        candidate = row[0].strip()
        if idx == 0 and candidate.lower() in {"domain", "domains", "name", "url"}:
            continue

        total_rows += 1
        domain = normalize_domain(candidate)

        if not domain or not DOMAIN_REGEX.match(domain):
            invalid_count += 1
            report_rows.append({"domain": candidate, "status": "invalid", "reason": "invalid domain format"})
            continue

        if domain in seen:
            report_rows.append({"domain": domain, "status": "duplicate", "reason": "duplicate in file"})
            continue

        seen.add(domain)
        tld = domain.split(".")[-1]
        domains_to_insert.append({
            "name": domain,
            "tld": tld,
            "registrar": None,
            "registered_at": None,
            "fetched_date": datetime.utcnow(),
            "check_status": DomainStatus.pending,
            "is_active": True,
        })

    imported_count = 0
    if domains_to_insert:
        existing_names = set()
        names = [d["name"] for d in domains_to_insert]
        for i in range(0, len(names), 1000):
            rows_chunk = db.query(Domain.name).filter(Domain.name.in_(names[i:i + 1000])).all()
            existing_names.update(r[0] for r in rows_chunk)

        insert_rows = []
        for d in domains_to_insert:
            if d["name"] in existing_names:
                report_rows.append({"domain": d["name"], "status": "duplicate", "reason": "already exists"})
            else:
                insert_rows.append(d)

        if insert_rows:
            for i in range(0, len(insert_rows), 500):
                batch = insert_rows[i:i + 500]
                result = db.execute(mysql_insert(Domain).values(batch).prefix_with("IGNORE"))
                imported_count += int(result.rowcount or 0)
                for item in batch:
                    report_rows.append({"domain": item["name"], "status": "imported", "reason": None})

        db.add(AuditLog(
            user_id=current_user.id,
            action=AuditAction.fetch_domains,
            description=f"CSV import: {imported_count} domains imported from {file.filename}",
            meta={
                "filename": file.filename,
                "total_rows": total_rows,
                "imported_count": imported_count,
            },
        ))
        db.commit()

        if imported_count > 0:
            try:
                from app.tasks.domain_tasks import queue_pending_seo_checks
                queue_pending_seo_checks.delay(limit=min(imported_count, 5000))
            except Exception:
                pass

    valid_rows = max(total_rows - invalid_count, 0)
    duplicate_count = max(total_rows - imported_count - invalid_count, 0)

    report_rows_sorted = sorted(
        report_rows,
        key=lambda x: 0 if x["status"] == "imported" else 1 if x["status"] == "duplicate" else 2,
    )
    max_report_rows = 500
    return {
        "filename": file.filename,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "imported_count": imported_count,
        "duplicate_count": duplicate_count,
        "invalid_count": invalid_count,
        "report_rows": report_rows_sorted[:max_report_rows],
        "report_truncated": len(report_rows_sorted) > max_report_rows,
    }


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
