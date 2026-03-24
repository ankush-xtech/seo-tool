"""
Domain Fetch + Full Background SEO Checks
Downloads from WhoisDS, stores all domains, checks ALL of them in background batches
"""

import base64
import zipfile
import io
import re
import logging
import time
import threading
from datetime import date, timedelta, datetime, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as req_lib
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert
from bs4 import BeautifulSoup

from app.db.session import get_db, SessionLocal
from app.middleware.deps import require_admin, get_current_user
from app.models.models import Domain, DomainStatus, SEOResult, AuditLog, AuditAction, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fetch", tags=["Domain Fetch"])

# ─── Global check progress tracker (in-memory) ───────────────────────────────
_check_progress = {
    "running": False,
    "total": 0,
    "done": 0,
    "failed": 0,
    "started_at": None,
}

# Track recently checked domains for real-time UI updates (ring buffer of last 50)
_recently_checked: list[dict] = []
_recently_checked_lock = threading.Lock()
MAX_RECENT = 50


def _add_recently_checked(domain_id: int, name: str, status: str, score: float,
                          verdict: str, email: str | None, phone: str | None):
    with _recently_checked_lock:
        _recently_checked.append({
            "id": domain_id,
            "name": name,
            "check_status": status,
            "seo_score": score,
            "verdict": verdict,
            "email": email,
            "phone": phone,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })
        # Keep only the last MAX_RECENT entries
        if len(_recently_checked) > MAX_RECENT:
            del _recently_checked[:-MAX_RECENT]


# ─── WhoisDS Download ─────────────────────────────────────────────────────────

def get_whoisds_url(target_date: date) -> str:
    filename = f"{target_date.strftime('%Y-%m-%d')}.zip"
    encoded  = base64.b64encode(filename.encode()).decode()
    return f"https://www.whoisds.com//whois-database/newly-registered-domains/{encoded}/nrd"


def download_domains_from_whoisds(target_date: date) -> list[dict]:
    url = get_whoisds_url(target_date)
    logger.info(f"[WhoisDS] Downloading for {target_date} — {url}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = req_lib.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except req_lib.exceptions.RequestException as e:
        logger.error(f"[WhoisDS] Download failed: {e}")
        return []
    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            data_files = [f for f in z.namelist() if not f.endswith("/")]
            if not data_files:
                return []
            with z.open(data_files[0]) as f:
                lines = f.read().decode("utf-8", errors="ignore").splitlines()
    except Exception as e:
        logger.error(f"[WhoisDS] ZIP error: {e}")
        return []

    domains = []
    for line in lines:
        line = line.strip().lower()
        if not line or "." not in line:
            continue
        tld = line.split(".")[-1]
        domains.append({"name": line, "tld": tld})
    logger.info(f"[WhoisDS] Parsed {len(domains):,} domains")
    return domains


def bulk_insert_domains(db: Session, domain_list: list[dict], fetch_date: datetime) -> dict:
    if not domain_list:
        return {"total_fetched": 0, "new_domains": 0, "duplicates_skipped": 0}
    total_fetched = len(domain_list)
    all_names = [d["name"] for d in domain_list]
    existing_names = set()
    for i in range(0, len(all_names), 1000):
        rows = db.query(Domain.name).filter(Domain.name.in_(all_names[i:i+1000])).all()
        existing_names.update(r[0] for r in rows)
    new_domains = [d for d in domain_list if d["name"] not in existing_names]
    inserted = 0
    for i in range(0, len(new_domains), 500):
        batch = new_domains[i:i+500]
        rows = [{"name": d["name"], "tld": d["tld"], "registrar": None,
                 "registered_at": None, "fetched_date": fetch_date,
                 "check_status": DomainStatus.pending, "is_active": True}
                for d in batch]
        result = db.execute(mysql_insert(Domain).values(rows).prefix_with("IGNORE"))
        db.flush()
        inserted += result.rowcount
    db.commit()
    return {"total_fetched": total_fetched, "new_domains": inserted,
            "duplicates_skipped": total_fetched - len(new_domains)}


# ─── Quick SEO Check (same as seo_audit.py) ──────────────────────────────────

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}')
IGNORED_EMAIL_DOMAINS = {
    "example.com","test.com","sentry.io","wixpress.com",
    "schema.org","w3.org","jquery.com","wordpress.org",
}


def quick_seo_check(domain: str) -> dict:
    result = {
        "domain": domain, "reachable": False, "score": 0,
        "verdict": "Unreachable", "title": "", "description": "",
        "email": None, "phone": None,
        "check_https": "fail", "check_meta": "fail",
        "check_h1": "fail", "check_viewport": "fail",
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}
    html = None
    for scheme in ["https", "http"]:
        try:
            resp = req_lib.get(f"{scheme}://{domain}", headers=headers,
                               timeout=8, allow_redirects=True)
            if resp.status_code == 200:
                html = resp.text
                result["check_https"] = "pass" if scheme == "https" else "fail"
                break
        except Exception:
            continue
    if not html:
        return result

    result["reachable"] = True
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""
    result["title"] = title[:80]
    result["check_title"] = "pass" if len(title) >= 30 else ("warn" if title else "fail")

    meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    desc = (meta.get("content") or "").strip() if meta else ""
    result["description"] = desc[:120]
    result["check_meta"] = "pass" if len(desc) >= 60 else ("warn" if desc else "fail")

    h1s = soup.find_all("h1")
    result["check_h1"] = "pass" if len(h1s) == 1 else ("warn" if len(h1s) > 1 else "fail")

    viewport = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
    result["check_viewport"] = "pass" if viewport else "fail"

    # Email
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if email and "@" in email and email.split("@")[-1] not in IGNORED_EMAIL_DOMAINS:
                result["email"] = email
                break
    if not result["email"]:
        for match in EMAIL_REGEX.finditer(html):
            email = match.group().lower()
            if (email.split("@")[-1] not in IGNORED_EMAIL_DOMAINS
                    and len(email) < 80
                    and not any(x in email for x in [".png", ".jpg", ".js"])):
                result["email"] = email
                break

    # Phone
    body = soup.find("body")
    body_text = body.get_text() if body else ""
    for match in PHONE_REGEX.finditer(body_text):
        phone = match.group().strip()
        digits = re.sub(r'\D', '', phone)
        if 8 <= len(digits) <= 15:
            result["phone"] = phone
            break

    # Score
    checks = [result["check_https"], result["check_meta"],
              result["check_h1"], result["check_viewport"]]
    score = sum(20 if c == "pass" else 10 if c == "warn" else 0 for c in checks)
    result["score"] = score
    result["verdict"] = ("Good Foundation" if score >= 75
                         else "Needs Improvement" if score >= 50
                         else "SEO Required")
    return result


# ─── Background: check ALL pending domains in batches ────────────────────────

def check_all_pending_domains_thread():
    """
    Runs in a daemon thread. Fetches pending domains in batches of 100,
    checks them with 10 threads, saves results. Keeps going until all done.
    """
    global _check_progress, _recently_checked
    _check_progress["running"] = True
    _check_progress["started_at"] = datetime.now(timezone.utc).isoformat()
    with _recently_checked_lock:
        _recently_checked.clear()

    BATCH = 100
    THREADS = 10

    db = SessionLocal()
    try:
        total_pending = db.query(Domain).filter(
            Domain.check_status == DomainStatus.pending).count()
        _check_progress["total"] = total_pending
        _check_progress["done"] = 0
        _check_progress["failed"] = 0
        logger.info(f"[AllCheck] Starting full check of {total_pending:,} pending domains")
    except Exception as e:
        logger.error(f"[AllCheck] Init error: {e}")
        db.close()
        _check_progress["running"] = False
        return
    finally:
        db.close()

    processed = 0
    while True:
        db = SessionLocal()
        try:
            batch = db.query(Domain).filter(
                Domain.check_status == DomainStatus.pending
            ).limit(BATCH).all()

            if not batch:
                logger.info(f"[AllCheck] All domains checked. Total processed: {processed:,}")
                break

            # Mark batch as running
            for d in batch:
                d.check_status = DomainStatus.running
            db.commit()

            domain_map = {d.name: d.id for d in batch}
            domain_names = list(domain_map.keys())
        except Exception as e:
            logger.error(f"[AllCheck] Batch fetch error: {e}")
            db.close()
            break
        finally:
            db.close()

        # Run checks in parallel
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            future_map = {executor.submit(quick_seo_check, name): name
                         for name in domain_names}
            for future in as_completed(future_map):
                name = future_map[future]
                domain_id = domain_map[name]
                save_db = SessionLocal()
                try:
                    r = future.result()
                    domain_obj = save_db.query(Domain).filter(Domain.id == domain_id).first()
                    if domain_obj:
                        domain_obj.seo_score = float(r["score"])
                        final_status = DomainStatus.done if r["reachable"] else DomainStatus.failed
                        domain_obj.check_status = final_status
                        seo = SEOResult(
                            domain_id=domain_id,
                            overall_score=float(r["score"]),
                            https_score=100.0 if r["check_https"] == "pass" else 0.0,
                            meta_score=100.0 if r["check_meta"] == "pass" else (50.0 if r["check_meta"] == "warn" else 0.0),
                            heading_score=100.0 if r["check_h1"] == "pass" else 0.0,
                            mobile_score=100.0 if r["check_viewport"] == "pass" else 0.0,
                            dns_data={
                                "title": r.get("title", ""),
                                "description": r.get("description", ""),
                                "email": r.get("email"),
                                "phone": r.get("phone"),
                                "verdict": r.get("verdict"),
                                "reachable": r.get("reachable"),
                            }
                        )
                        save_db.add(seo)
                        save_db.commit()
                        processed += 1
                        if r["reachable"]:
                            _check_progress["done"] += 1
                        else:
                            _check_progress["failed"] += 1

                        # Track for real-time UI updates
                        _add_recently_checked(
                            domain_id=domain_id,
                            name=name,
                            status=final_status.value,
                            score=float(r["score"]),
                            verdict=r.get("verdict", "Unreachable"),
                            email=r.get("email"),
                            phone=r.get("phone"),
                        )
                except Exception as e:
                    logger.error(f"[AllCheck] Save error for {name}: {e}")
                    save_db.rollback()
                    try:
                        d = save_db.query(Domain).filter(Domain.id == domain_id).first()
                        if d:
                            d.check_status = DomainStatus.failed
                            save_db.commit()
                    except Exception:
                        pass
                    _check_progress["failed"] += 1
                finally:
                    save_db.close()

        logger.info(f"[AllCheck] Progress: {processed:,}/{_check_progress['total']:,}")

    _check_progress["running"] = False
    logger.info(f"[AllCheck] Complete. Done: {_check_progress['done']:,} Failed: {_check_progress['failed']:,}")


# ─── API Endpoints ────────────────────────────────────────────────────────────

@router.post("/run")
def run_fetch_now(
    background_tasks: BackgroundTasks,
    fetch_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    1. Download all domains from WhoisDS (~70,000)
    2. Store all in database
    3. Start checking ALL pending domains in background (batches of 100)
    """
    global _check_progress
    start = time.time()

    target_date = date.today() - timedelta(days=1)
    if fetch_date:
        try:
            target_date = date.fromisoformat(fetch_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="fetch_date must be YYYY-MM-DD")

    # Download and store
    domain_list = download_domains_from_whoisds(target_date)
    if not domain_list:
        return {
            "status": "no_data",
            "message": f"No domains found for {target_date}. Try a different date.",
            "total_fetched": 0, "new_domains": 0, "duplicates_skipped": 0,
            "duration_seconds": round(time.time() - start, 2),
            "fetch_date": str(target_date),
        }

    stats = bulk_insert_domains(db, domain_list, datetime.now(timezone.utc))

    # Audit log
    db.add(AuditLog(
        user_id=admin.id,
        action=AuditAction.fetch_domains,
        description=f"WhoisDS fetch {target_date}: {stats['new_domains']} new domains",
        meta={"fetch_date": str(target_date), **stats}
    ))
    db.commit()

    # Count total pending
    total_pending = db.query(Domain).filter(
        Domain.check_status == DomainStatus.pending).count()

    # Start background check of ALL pending domains
    if not _check_progress["running"] and total_pending > 0:
        t = threading.Thread(target=check_all_pending_domains_thread, daemon=True)
        t.start()
        logger.info(f"[Fetch] Started background check thread for {total_pending:,} domains")

    duration = round(time.time() - start, 2)
    return {
        "status": "success",
        "message": f"Fetched {stats['new_domains']} new domains. Checking ALL {total_pending:,} pending domains in background…",
        "fetch_date": str(target_date),
        "duration_seconds": duration,
        "total_pending_check": total_pending,
        **stats,
    }


@router.get("/check-progress")
def get_check_progress(
    since: Optional[str] = Query(None, description="ISO timestamp — only return domains checked after this time"),
    _: User = Depends(get_current_user),
):
    """Returns live progress of the background SEO check + recently checked domains."""
    prog = _check_progress.copy()
    pending_in_db = 0
    running_in_db = 0
    db = SessionLocal()
    try:
        pending_in_db = db.query(Domain).filter(
            Domain.check_status.in_([DomainStatus.pending, DomainStatus.running])
        ).count()
        running_in_db = db.query(Domain).filter(
            Domain.check_status == DomainStatus.running
        ).count()
    finally:
        db.close()

    # Return recently checked domains (optionally filtered by timestamp)
    with _recently_checked_lock:
        if since:
            recent = [d for d in _recently_checked if d["checked_at"] > since]
        else:
            recent = list(_recently_checked[-20:])  # default: last 20

    return {
        **prog,
        "pending_in_db": pending_in_db,
        "running_in_db": running_in_db,
        "percent": round(
            (prog["done"] + prog["failed"]) / prog["total"] * 100, 1
        ) if prog["total"] > 0 else 0,
        "recently_checked": recent,
    }


@router.post("/check-pending")
def trigger_check_pending(
    _: User = Depends(require_admin),
):
    """Manually start checking all pending domains (if not already running)."""
    global _check_progress
    if _check_progress["running"]:
        return {
            "message": "Already running",
            "done": _check_progress["done"],
            "total": _check_progress["total"],
        }

    db = SessionLocal()
    try:
        total_pending = db.query(Domain).filter(
            Domain.check_status == DomainStatus.pending).count()
    finally:
        db.close()

    if total_pending == 0:
        return {"message": "No pending domains to check", "count": 0}

    t = threading.Thread(target=check_all_pending_domains_thread, daemon=True)
    t.start()
    return {"message": f"Started checking {total_pending:,} pending domains", "count": total_pending}


@router.get("/available-dates")
def get_available_dates(_: User = Depends(require_admin)):
    today = date.today()
    return {"dates": [
        {"date": str(today - timedelta(days=i)),
         "label": "Yesterday" if i == 1 else f"{i} days ago"}
        for i in range(1, 8)
    ]}
