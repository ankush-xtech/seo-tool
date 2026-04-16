"""
Outreach Pipeline: SEO Check → Generate Email → Send → Track
Runs 13-point SEO checks on Maps listings, generates personalized emails,
sends via SendGrid, and tracks opens/clicks/replies.
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException, Query
from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db, SessionLocal
from app.middleware.deps import require_admin, get_current_user
from app.models.models import (
    BusinessListing, ListingSEOCheck, OutreachEmail,
    SEOCheckStatus, OutreachEmailStatus,
    AuditLog, AuditAction, User, MapSearchQuery,
)
from app.schemas.outreach import (
    LeadPublic, LeadList, OutreachStats, SendEmailsRequest, EmailPreview,
    SendSelectedEmailsRequest,
)
from app.services.maps.listing_seo_checker import run_seo_check
from app.services.maps.outreach_email import (
    generate_email, get_seo_problems, send_email, _generate_template_email, inject_tracking,
)
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outreach", tags=["Outreach"])

# ─── Global progress tracker ─────────────────────────────────────────────────

_seo_progress = {
    "running": False,
    "total": 0,
    "done": 0,
    "failed": 0,
    "started_at": None,
}
_seo_progress_lock = threading.Lock()

_recently_checked: list[dict] = []
_recently_lock = threading.Lock()


# ─── Background SEO check thread ─────────────────────────────────────────────

def _seo_check_thread(listing_ids: list[int]):
    """Run 13-point SEO check on a batch of listings in background."""
    db = SessionLocal()
    try:
        with _seo_progress_lock:
            _seo_progress["running"] = True
            _seo_progress["total"] = len(listing_ids)
            _seo_progress["done"] = 0
            _seo_progress["failed"] = 0
            _seo_progress["started_at"] = datetime.now(timezone.utc).isoformat()

        with _recently_lock:
            _recently_checked.clear()

        def _check_one(lid: int):
            check_db = SessionLocal()
            try:
                listing = check_db.query(BusinessListing).filter(BusinessListing.id == lid).first()
                if not listing or not listing.website:
                    return

                # Create or get existing SEO check
                seo = check_db.query(ListingSEOCheck).filter(
                    ListingSEOCheck.business_listing_id == lid
                ).first()
                if not seo:
                    seo = ListingSEOCheck(business_listing_id=lid)
                    check_db.add(seo)

                seo.status = SEOCheckStatus.running
                check_db.commit()

                # Run the 13-point check
                result = run_seo_check(
                    website=listing.website,
                    business_name=listing.business_name or "",
                    phone=listing.phone or "",
                )

                # Save results
                for key, val in result.items():
                    if hasattr(seo, key):
                        setattr(seo, key, val)
                seo.status = SEOCheckStatus.done
                seo.checked_at = datetime.now(timezone.utc)
                check_db.commit()

                with _recently_lock:
                    _recently_checked.append({
                        "listing_id": lid,
                        "business_name": listing.business_name,
                        "website": listing.website,
                        "seo_score": result["overall_score"],
                        "verdict": result["verdict"],
                    })
                    if len(_recently_checked) > 50:
                        del _recently_checked[:-50]

                with _seo_progress_lock:
                    _seo_progress["done"] += 1

            except Exception as e:
                logger.error(f"SEO check failed for listing {lid}: {e}")
                try:
                    seo = check_db.query(ListingSEOCheck).filter(
                        ListingSEOCheck.business_listing_id == lid
                    ).first()
                    if seo:
                        seo.status = SEOCheckStatus.failed
                        seo.error_message = str(e)[:500]
                        check_db.commit()
                except Exception:
                    pass
                with _seo_progress_lock:
                    _seo_progress["failed"] += 1
            finally:
                check_db.close()

        with ThreadPoolExecutor(max_workers=settings.OUTREACH_SEO_WORKERS) as executor:
            futures = [executor.submit(_check_one, lid) for lid in listing_ids]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    pass

    finally:
        with _seo_progress_lock:
            _seo_progress["running"] = False
        db.close()
        logger.info(f"SEO check batch complete: {_seo_progress['done']} done, {_seo_progress['failed']} failed")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/run-seo-check")
def start_seo_check(
    search_query_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Run 13-point SEO check on all Maps listings that have websites."""
    with _seo_progress_lock:
        if _seo_progress["running"]:
            raise HTTPException(409, "SEO check already running")

    q = db.query(BusinessListing).filter(
        BusinessListing.website.isnot(None),
        BusinessListing.website != "",
    )
    if search_query_id:
        q = q.filter(BusinessListing.search_query_id == search_query_id)

    # Only check listings that haven't been checked or failed
    q = q.outerjoin(ListingSEOCheck).filter(
        (ListingSEOCheck.id.is_(None)) | (ListingSEOCheck.status == SEOCheckStatus.failed)
    )

    listing_ids = [lid for (lid,) in q.with_entities(BusinessListing.id).all()]

    if not listing_ids:
        raise HTTPException(400, "No unchecked listings with websites found")

    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.outreach_seo_check,
        description=f"Started SEO check on {len(listing_ids)} listings",
    ))
    db.commit()

    thread = threading.Thread(target=_seo_check_thread, args=(listing_ids,), daemon=True)
    thread.start()

    return {"status": "started", "total": len(listing_ids)}


@router.get("/tracking-status")
def tracking_status(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Full tracking debug — config + DB stats + last email pixel check."""
    base_url = settings.TRACKING_BASE_URL

    # Count tracking stats from DB
    total   = db.query(OutreachEmail).count()
    sent    = db.query(OutreachEmail).filter(OutreachEmail.status == OutreachEmailStatus.sent).count()
    opened  = db.query(OutreachEmail).filter(OutreachEmail.opened_at.isnot(None)).count()
    clicked = db.query(OutreachEmail).filter(OutreachEmail.clicked_at.isnot(None)).count()

    # Check if latest email has pixel injected
    latest = db.query(OutreachEmail).order_by(OutreachEmail.id.desc()).first()
    latest_info = None
    if latest:
        pixel_in_body = f"/track/open/{latest.id}" in (latest.body_html or "")
        latest_info = {
            "id": latest.id,
            "to": latest.to_email,
            "status": latest.status.value if latest.status else None,
            "sent_at": str(latest.sent_at) if latest.sent_at else None,
            "opened_at": str(latest.opened_at) if latest.opened_at else None,
            "clicked_at": str(latest.clicked_at) if latest.clicked_at else None,
            "pixel_injected_in_body": pixel_in_body,
            "fix_if_false": "Restart backend → send a new email → pixel will be in it",
        }

    return {
        "tracking_enabled": bool(base_url),
        "tracking_base_url": base_url or "❌ NOT SET — add TRACKING_BASE_URL to .env and restart",
        "pixel_url_example": f"{base_url}/track/open/1" if base_url else None,
        "click_url_example": f"{base_url}/track/click/1?to=https://example.com" if base_url else None,
        "db_stats": {
            "total_emails": total,
            "status_sent": sent,
            "opened": opened,
            "clicked": clicked,
        },
        "latest_email": latest_info,
        "public_debug_url": f"{base_url}/track/debug" if base_url else None,
    }


@router.get("/seo-progress")
def get_seo_progress(current_user: User = Depends(get_current_user)):
    """Get real-time progress of SEO checking."""
    with _seo_progress_lock:
        progress = dict(_seo_progress)
    with _recently_lock:
        progress["recently_checked"] = list(_recently_checked[-20:])
    if progress["total"] > 0:
        progress["percent"] = round(
            (progress["done"] + progress["failed"]) / progress["total"] * 100, 1
        )
    else:
        progress["percent"] = 0
    return progress


@router.get("/leads", response_model=LeadList)
def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search_query_id: Optional[int] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    has_email: Optional[bool] = None,
    max_score: Optional[int] = None,
    min_score: Optional[int] = None,
    email_status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List leads with SEO scores and email status for the outreach dashboard."""
    q = db.query(BusinessListing).options(
        joinedload(BusinessListing.seo_check),
    ).outerjoin(ListingSEOCheck)

    if search_query_id:
        q = q.filter(BusinessListing.search_query_id == search_query_id)
    if category:
        q = q.filter(BusinessListing.category.ilike(f"%{category}%"))
    if city:
        q = q.filter(BusinessListing.city.ilike(f"%{city}%"))
    if has_email:
        q = q.filter(BusinessListing.email.isnot(None), BusinessListing.email != "")
    if max_score is not None:
        q = q.filter(ListingSEOCheck.overall_score <= max_score)
    if min_score is not None:
        q = q.filter(ListingSEOCheck.overall_score >= min_score)
    if search:
        q = q.filter(BusinessListing.business_name.ilike(f"%{search}%"))

    # Filter by email status
    if email_status:
        q = q.outerjoin(OutreachEmail).filter(OutreachEmail.status == email_status)

    total = q.count()
    listings = q.order_by(BusinessListing.id.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    items = []
    for listing in listings:
        seo = listing.seo_check
        # Get latest outreach email
        latest_email = db.query(OutreachEmail).filter(
            OutreachEmail.business_listing_id == listing.id
        ).order_by(OutreachEmail.created_at.desc()).first()

        items.append(LeadPublic(
            listing_id=listing.id,
            business_name=listing.business_name,
            website=listing.website,
            city=listing.city,
            category=listing.category,
            email=listing.email,
            phone=listing.phone,
            seo_score=seo.overall_score if seo else None,
            seo_verdict=seo.verdict if seo else None,
            seo_status=seo.status.value if seo else None,
            email_status=latest_email.status.value if latest_email else None,
            email_sent_at=latest_email.sent_at if latest_email else None,
            email_opened_at=latest_email.opened_at if latest_email else None,
            email_clicked_at=latest_email.clicked_at if latest_email else None,
            email_replied_at=latest_email.replied_at if latest_email else None,
            preview_url=latest_email.preview_url if latest_email else None,
        ))

    return LeadList(items=items, total=total, page=page, per_page=per_page)


@router.get("/stats", response_model=OutreachStats)
def get_stats(
    search_query_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get outreach pipeline stats."""
    q = db.query(BusinessListing)
    if search_query_id:
        q = q.filter(BusinessListing.search_query_id == search_query_id)

    total = q.count()
    with_website = q.filter(BusinessListing.website.isnot(None), BusinessListing.website != "").count()
    with_email = q.filter(BusinessListing.email.isnot(None), BusinessListing.email != "").count()

    seo_checked = db.query(ListingSEOCheck).filter(ListingSEOCheck.status == SEOCheckStatus.done).count()
    score_below_70 = db.query(ListingSEOCheck).filter(
        ListingSEOCheck.status == SEOCheckStatus.done,
        ListingSEOCheck.overall_score < settings.OUTREACH_SCORE_THRESHOLD,
    ).count()

    sent = db.query(OutreachEmail).filter(OutreachEmail.status != OutreachEmailStatus.draft).count()
    opened = db.query(OutreachEmail).filter(OutreachEmail.opened_at.isnot(None)).count()
    clicked = db.query(OutreachEmail).filter(OutreachEmail.clicked_at.isnot(None)).count()
    replied = db.query(OutreachEmail).filter(OutreachEmail.status == OutreachEmailStatus.replied).count()

    return OutreachStats(
        total_leads=total,
        with_website=with_website,
        with_email=with_email,
        seo_checked=seo_checked,
        score_below_70=score_below_70,
        emails_sent=sent,
        emails_opened=opened,
        emails_clicked=clicked,
        emails_replied=replied,
        open_rate=round(opened / sent * 100, 1) if sent else 0,
        reply_rate=round(replied / sent * 100, 1) if sent else 0,
    )


@router.post("/preview-emails", response_model=list[EmailPreview])
def preview_emails(
    data: SendEmailsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Preview emails that would be sent (without actually sending)."""
    leads = _get_eligible_leads(db, data)
    previews = []

    for listing, seo in leads[:10]:  # Preview max 10
        check_dict = {col: getattr(seo, col) for col in [
            "check_ssl", "check_robots", "check_sitemap", "check_canonical",
            "check_mobile", "check_speed", "load_time", "check_h1",
            "check_title", "title_length", "check_description", "description_length",
            "check_alt_tags", "images_total", "images_missing_alt",
            "check_business_name", "check_phone", "check_local_schema",
            "check_social_links", "check_contact_page",
        ]}
        problems = get_seo_problems(check_dict)
        email_data = generate_email(
            business_name=listing.business_name,
            website=listing.website or "",
            city=listing.city or "",
            seo_score=seo.overall_score,
            problems=problems,
            from_name=settings.OUTREACH_FROM_NAME,
            category=listing.category or "",
            rating=getattr(listing, "rating", None),
            reviews_count=getattr(listing, "reviews_count", None),
        )

        previews.append(EmailPreview(
            listing_id=listing.id,
            business_name=listing.business_name,
            to_email=listing.email,
            subject=email_data["subject"],
            body_html=email_data["body_html"],
            seo_score=seo.overall_score,
            problems=problems,
        ))

    return previews


@router.post("/send-emails")
def send_emails(
    data: SendEmailsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Generate and send AI-personalised outreach emails to eligible leads (score < 70 + has email).

    Requires at least one AI key (ANTHROPIC_API_KEY or GROQ_API_KEY) — no template fallback.
    Problems are fetched from each business's real SEO audit results (not dummy data).
    """
    # ── Guard: email sending provider ───────────────────────────────────────
    if not settings.SENDGRID_API_KEY and not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        raise HTTPException(400, "No email provider configured. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD (Gmail) or SENDGRID_API_KEY in .env")

    # ── Guard: AI key required ───────────────────────────────────────────────
    if not settings.ANTHROPIC_API_KEY and not settings.GROQ_API_KEY:
        raise HTTPException(
            400,
            "No AI provider configured. Add ANTHROPIC_API_KEY (paid) or GROQ_API_KEY (free) "
            "to your .env file — emails are AI-only."
        )

    leads = _get_eligible_leads(db, data)
    if not leads:
        raise HTTPException(400, "No eligible leads found (score < 70 with email, not yet emailed)")

    sent_count = 0
    failed_count = 0
    errors = []

    for listing, seo in leads:
        try:
            recipient_email, email_error = _normalize_recipient_email(listing.email)
            if email_error:
                failed_count += 1
                errors.append(f"{listing.business_name}: invalid email '{listing.email}' ({email_error})")
                continue

            # ── Build real SEO problems from this business's actual audit ──
            check_dict = {col: getattr(seo, col) for col in [
                "check_ssl", "check_robots", "check_sitemap", "check_canonical",
                "check_mobile", "check_speed", "load_time", "check_h1",
                "check_title", "title_length", "check_description", "description_length",
                "check_alt_tags", "images_total", "images_missing_alt",
                "check_business_name", "check_phone", "check_local_schema",
                "check_social_links", "check_contact_page",
            ]}
            problems = get_seo_problems(check_dict)

            # ── Generate AI email using real business data + real problems ─
            email_data = generate_email(
                business_name=listing.business_name,
                website=listing.website or "",
                city=listing.city or "",
                seo_score=seo.overall_score,
                problems=problems,
                from_name=settings.OUTREACH_FROM_NAME,
                category=listing.category or "",
                rating=getattr(listing, "rating", None),
                reviews_count=getattr(listing, "reviews_count", None),
            )

            # ── Save first (draft) so we get the DB id for tracking URLs ──
            outreach = OutreachEmail(
                business_listing_id=listing.id,
                seo_check_id=seo.id,
                to_email=recipient_email,
                subject=email_data["subject"],
                body_html=email_data["body_html"],
                status=OutreachEmailStatus.draft,
            )
            db.add(outreach)
            db.flush()  # assigns outreach.id without committing

            # ── Inject tracking pixel + click tracking if configured ───────
            body_to_send = email_data["body_html"]
            if settings.TRACKING_BASE_URL:
                body_to_send = inject_tracking(body_to_send, outreach.id, settings.TRACKING_BASE_URL)
                outreach.body_html = body_to_send
                logger.info(f"[TRACKING] Pixel injected for email id={outreach.id} → {settings.TRACKING_BASE_URL}/track/open/{outreach.id}")
            else:
                logger.warning("[TRACKING] TRACKING_BASE_URL not set — tracking pixel NOT injected. Set it in .env and restart.")

            # ── Send via configured provider (SendGrid or Gmail SMTP) ─────
            message_id = send_email(
                to_email=recipient_email,
                subject=email_data["subject"],
                body_html=body_to_send,
            )

            # ── Update status after send ───────────────────────────────────
            outreach.status = OutreachEmailStatus.sent if message_id else OutreachEmailStatus.draft
            outreach.sendgrid_message_id = message_id
            outreach.sent_at = datetime.now(timezone.utc) if message_id else None
            db.commit()

            if message_id:
                sent_count += 1
            else:
                failed_count += 1
                errors.append(f"{listing.business_name}: email sent but no message ID returned")

        except Exception as e:
            db.rollback()
            err_msg = f"{listing.business_name} ({listing.email or 'no-email'}): {type(e).__name__}: {e}"
            logger.error(f"Failed to send email — {err_msg}")
            errors.append(err_msg)
            failed_count += 1

    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.outreach_email_sent,
        description=f"Sent {sent_count} outreach emails ({failed_count} failed)",
    ))
    db.commit()

    result = {"sent": sent_count, "failed": failed_count, "total": len(leads)}
    if errors:
        result["errors"] = errors
    return result


@router.get("/default-prompt")
def get_default_prompt(current_user: User = Depends(require_admin)):
    """Return the default website generation prompt template with placeholder variables."""
    from app.services.maps.preview_site_generator import get_default_prompt_template
    return {"prompt": get_default_prompt_template()}


@router.post("/generate-previews")
def generate_previews(
    data: SendSelectedEmailsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Generate preview websites for selected businesses and deploy to Vercel.

    Does NOT send any email. Just generates + deploys preview sites so admin
    can review them before sending. The preview_url is stored in a draft
    OutreachEmail record so it can be reused when actually sending.
    """
    if not data.listing_ids:
        raise HTTPException(400, "No listing IDs provided")
    if len(data.listing_ids) > 20:
        raise HTTPException(400, "Max 20 businesses per preview batch")

    # Guards
    if not settings.VERCEL_API_TOKEN:
        raise HTTPException(400, "VERCEL_API_TOKEN not configured in .env")
    if not settings.GROQ_API_KEY and not settings.ANTHROPIC_API_KEY:
        raise HTTPException(400, "No AI provider configured (GROQ_API_KEY or ANTHROPIC_API_KEY)")

    rows = db.query(BusinessListing, ListingSEOCheck).join(
        ListingSEOCheck,
        ListingSEOCheck.business_listing_id == BusinessListing.id,
    ).filter(
        BusinessListing.id.in_(data.listing_ids),
        BusinessListing.email.isnot(None),
        BusinessListing.email != "",
        ListingSEOCheck.status == SEOCheckStatus.done,
    ).all()

    if not rows:
        raise HTTPException(400, "None of the selected businesses have email + completed SEO check.")

    from app.services.maps.preview_site_generator import generate_preview_site
    from app.services.maps.vercel_deployer import deploy_to_vercel

    # ── Prepare data for parallel processing (read DB data before threads) ──
    jobs = []
    for listing, seo in rows:
        check_dict = {col: getattr(seo, col) for col in [
            "check_ssl", "check_robots", "check_sitemap", "check_canonical",
            "check_mobile", "check_speed", "load_time", "check_h1",
            "check_title", "title_length", "check_description", "description_length",
            "check_alt_tags", "images_total", "images_missing_alt",
            "check_business_name", "check_phone", "check_local_schema",
            "check_social_links", "check_contact_page",
        ]}
        problems = get_seo_problems(check_dict)
        jobs.append({
            "listing_id": listing.id,
            "business_name": listing.business_name,
            "website": listing.website or "",
            "city": listing.city or "",
            "category": listing.category or "",
            "phone": listing.phone,
            "email": listing.email,
            "seo_score": seo.overall_score,
            "seo_id": seo.id,
            "problems": problems,
        })

    # ── Build per-business custom prompt if provided ─────────────────────
    custom_prompt_template = data.custom_prompt

    def _resolve_custom_prompt(template: str, job: dict) -> str:
        """Replace placeholder variables in the custom prompt with actual business data."""
        return (
            template
            .replace("{business_name}", job["business_name"])
            .replace("{website}", job["website"])
            .replace("{city}", job["city"])
            .replace("{category}", job["category"])
            .replace("{phone}", job["phone"] or "N/A")
            .replace("{email}", job["email"] or "N/A")
        )

    # ── Generate + deploy sequentially ─────────────────────────────────
    def _generate_and_deploy(job: dict) -> dict:
        """Thread worker: generate HTML with AI + deploy to Vercel."""
        try:
            resolved_prompt = (
                _resolve_custom_prompt(custom_prompt_template, job)
                if custom_prompt_template
                else None
            )
            site_html = generate_preview_site(
                business_name=job["business_name"],
                website=job["website"],
                city=job["city"],
                category=job["category"],
                seo_score=job["seo_score"],
                problems=job["problems"],
                phone=job["phone"],
                email=job["email"],
                custom_prompt=resolved_prompt,
                hero_image_url=data.hero_image_url,
                about_image_url=data.about_image_url,
            )
            if not site_html:
                return {**job, "preview_url": None, "error": "AI returned empty HTML"}

            preview_url = deploy_to_vercel(
                html_content=site_html,
                site_name=job["business_name"],
            )
            if not preview_url:
                return {**job, "preview_url": None, "error": "Vercel deployment failed"}

            return {**job, "preview_url": preview_url, "error": None}
        except Exception as e:
            return {**job, "preview_url": None, "error": str(e)}

    # Groq free tier: 30 RPM, 6,000 TPM — each site uses ~10k tokens
    # Sequential is safest to avoid rate limits. Add small delay between calls.
    import time
    completed_jobs = []

    for i, job in enumerate(jobs):
        if i > 0:
            time.sleep(2)  # 2s delay between calls to stay under rate limits
        completed_jobs.append(_generate_and_deploy(job))

    # ── Save results to DB (sequential — DB sessions aren't thread-safe) ──
    generated = 0
    failed = 0
    errors = []
    results = []

    for job in completed_jobs:
        if job["error"]:
            failed += 1
            errors.append(f"{job['business_name']}: {job['error']}")
            logger.error(f"Preview failed for {job['business_name']}: {job['error']}")
            continue

        try:
            existing = db.query(OutreachEmail).filter(
                OutreachEmail.business_listing_id == job["listing_id"],
            ).order_by(OutreachEmail.created_at.desc()).first()

            if existing:
                existing.preview_url = job["preview_url"]
            else:
                draft = OutreachEmail(
                    business_listing_id=job["listing_id"],
                    seo_check_id=job["seo_id"],
                    to_email=job["email"],
                    subject="(preview pending)",
                    body_html="(preview pending)",
                    status=OutreachEmailStatus.draft,
                    preview_url=job["preview_url"],
                )
                db.add(draft)

            db.commit()
            generated += 1
            results.append({
                "listing_id": job["listing_id"],
                "business_name": job["business_name"],
                "preview_url": job["preview_url"],
            })
        except Exception as e:
            db.rollback()
            failed += 1
            errors.append(f"{job['business_name']}: DB save error: {e}")

    result = {"generated": generated, "failed": failed, "total": len(rows), "previews": results}
    if errors:
        result["errors"] = errors
    return result


@router.post("/send-selected-emails")
def send_selected_emails(
    data: SendSelectedEmailsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Send emails to a specific list of businesses selected by checkbox.

    mode='ai'       → AI-generated email (Anthropic or Groq, auto-detected)
    mode='template' → Static HTML template email (no AI key needed)

    Requires the business to have a valid email and a completed SEO check.
    """
    if not data.listing_ids:
        raise HTTPException(400, "No listing IDs provided")

    if len(data.listing_ids) > 100:
        raise HTTPException(400, "Max 100 businesses per batch")

    if data.mode not in ("ai", "template"):
        raise HTTPException(400, "mode must be 'ai' or 'template'")

    # ── Guard: AI key required for AI mode ───────────────────────────────────
    if data.mode == "ai" and not settings.ANTHROPIC_API_KEY and not settings.GROQ_API_KEY:
        raise HTTPException(
            400,
            "No AI provider configured. Add ANTHROPIC_API_KEY or GROQ_API_KEY to .env"
        )

    # ── Guard: preview requires Vercel token ───────────────────────────────
    if data.with_preview and not settings.VERCEL_API_TOKEN:
        raise HTTPException(
            400,
            "Preview sites require VERCEL_API_TOKEN. Add it to .env or disable preview."
        )

    # ── Guard: email sending provider ────────────────────────────────────────
    if not settings.SENDGRID_API_KEY and not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        raise HTTPException(400, "No email provider configured. Set SMTP or SENDGRID in .env")

    # ── Fetch selected listings that have email + completed SEO check ─────────
    rows = db.query(BusinessListing, ListingSEOCheck).join(
        ListingSEOCheck,
        ListingSEOCheck.business_listing_id == BusinessListing.id,
    ).filter(
        BusinessListing.id.in_(data.listing_ids),
        BusinessListing.email.isnot(None),
        BusinessListing.email != "",
        ListingSEOCheck.status == SEOCheckStatus.done,
    ).all()

    if not rows:
        raise HTTPException(
            400,
            "None of the selected businesses have both a valid email and a completed SEO check. "
            "Run SEO check first."
        )

    sent_count = 0
    failed_count = 0
    skipped_count = 0
    previews_generated = 0
    errors = []

    for listing, seo in rows:
        try:
            recipient_email, email_error = _normalize_recipient_email(listing.email)
            if email_error:
                failed_count += 1
                errors.append(f"{listing.business_name}: invalid email '{listing.email}' ({email_error})")
                continue

            # ── Build real SEO problems from this business's audit ─────────
            check_dict = {col: getattr(seo, col) for col in [
                "check_ssl", "check_robots", "check_sitemap", "check_canonical",
                "check_mobile", "check_speed", "load_time", "check_h1",
                "check_title", "title_length", "check_description", "description_length",
                "check_alt_tags", "images_total", "images_missing_alt",
                "check_business_name", "check_phone", "check_local_schema",
                "check_social_links", "check_contact_page",
            ]}
            problems = get_seo_problems(check_dict)

            # ── Generate email based on mode ──────────────────────────────
            if data.mode == "ai":
                from app.services.maps.ai_email_generator import generate_ai_email
                email_data = generate_ai_email(
                    business_name=listing.business_name,
                    website=listing.website or "",
                    city=listing.city or "",
                    category=listing.category or "",
                    seo_score=seo.overall_score,
                    problems=problems,
                    from_name=settings.OUTREACH_FROM_NAME,
                    rating=getattr(listing, "rating", None),
                    reviews_count=getattr(listing, "reviews_count", None),
                )
            else:
                # Template mode — always works, no AI key needed
                email_data = _generate_template_email(
                    business_name=listing.business_name,
                    website=listing.website or "",
                    city=listing.city or "",
                    seo_score=seo.overall_score,
                    problems=problems,
                    from_name=settings.OUTREACH_FROM_NAME,
                )

            if not email_data:
                raise RuntimeError("Email generator returned empty result")

            # ── Attach preview URL if one was pre-generated ────────────
            preview_url = None
            if data.with_preview:
                # Check if a preview URL already exists (from /generate-previews)
                existing_draft = db.query(OutreachEmail).filter(
                    OutreachEmail.business_listing_id == listing.id,
                    OutreachEmail.preview_url.isnot(None),
                ).order_by(OutreachEmail.created_at.desc()).first()

                if existing_draft and existing_draft.preview_url:
                    preview_url = existing_draft.preview_url
                    previews_generated += 1
                    logger.info(f"Reusing existing preview URL: {preview_url}")
                else:
                    # No pre-generated preview — generate on the fly
                    try:
                        from app.services.maps.preview_site_generator import generate_preview_site
                        from app.services.maps.vercel_deployer import deploy_to_vercel

                        # Resolve custom prompt if provided
                        resolved = None
                        if data.custom_prompt:
                            resolved = (
                                data.custom_prompt
                                .replace("{business_name}", listing.business_name)
                                .replace("{website}", listing.website or "")
                                .replace("{city}", listing.city or "")
                                .replace("{category}", listing.category or "")
                                .replace("{phone}", listing.phone or "N/A")
                                .replace("{email}", listing.email or "N/A")
                            )

                        site_html = generate_preview_site(
                            business_name=listing.business_name,
                            website=listing.website or "",
                            city=listing.city or "",
                            category=listing.category or "",
                            seo_score=seo.overall_score,
                            problems=problems,
                            phone=listing.phone,
                            email=listing.email,
                            custom_prompt=resolved,
                            hero_image_url=data.hero_image_url,
                            about_image_url=data.about_image_url,
                        )
                        if site_html:
                            preview_url = deploy_to_vercel(html_content=site_html, site_name=listing.business_name)
                            if preview_url:
                                previews_generated += 1
                    except Exception as e:
                        logger.error(f"Preview generation error for {listing.business_name}: {e}")

                # Inject preview CTA button into email if we have a URL
                if preview_url:
                    from app.services.maps.outreach_email import inject_preview_button
                    email_data["body_html"] = inject_preview_button(email_data["body_html"], preview_url)

            # ── Save first (draft) so we get the DB id for tracking URLs ──
            outreach = OutreachEmail(
                business_listing_id=listing.id,
                seo_check_id=seo.id,
                to_email=recipient_email,
                subject=email_data["subject"],
                body_html=email_data["body_html"],
                status=OutreachEmailStatus.draft,
                preview_url=preview_url,
            )
            db.add(outreach)
            db.flush()  # assigns outreach.id without committing

            # ── Inject tracking pixel + click tracking if configured ───────
            body_to_send = email_data["body_html"]
            if settings.TRACKING_BASE_URL:
                body_to_send = inject_tracking(body_to_send, outreach.id, settings.TRACKING_BASE_URL)
                outreach.body_html = body_to_send
                logger.info(f"[TRACKING] Pixel injected for email id={outreach.id} → {settings.TRACKING_BASE_URL}/track/open/{outreach.id}")
            else:
                logger.warning("[TRACKING] TRACKING_BASE_URL not set — tracking pixel NOT injected. Set it in .env and restart.")

            # ── Send ──────────────────────────────────────────────────────
            message_id = send_email(
                to_email=recipient_email,
                subject=email_data["subject"],
                body_html=body_to_send,
            )

            # ── Update status after send ───────────────────────────────────
            outreach.status = OutreachEmailStatus.sent if message_id else OutreachEmailStatus.draft
            outreach.sendgrid_message_id = message_id
            outreach.sent_at = datetime.now(timezone.utc) if message_id else None
            db.commit()

            if message_id:
                sent_count += 1
            else:
                failed_count += 1

        except Exception as e:
            db.rollback()
            err_msg = f"{listing.business_name} ({listing.email or 'no-email'}): {type(e).__name__}: {e}"
            logger.error(f"send-selected-emails failed — {err_msg}")
            errors.append(err_msg)
            failed_count += 1

    # IDs that were requested but had no email / no SEO check
    fetched_ids = {listing.id for listing, _ in rows}
    skipped_count = len([i for i in data.listing_ids if i not in fetched_ids])

    result: dict = {
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "previews_generated": previews_generated,
        "total_requested": len(data.listing_ids),
        "mode": data.mode,
    }
    if errors:
        result["errors"] = errors
    return result


@router.put("/emails/{email_id}/status")
def update_email_status(
    email_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Manually update email status (e.g., mark as replied)."""
    email = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
    if not email:
        raise HTTPException(404, "Email not found")

    now = datetime.now(timezone.utc)
    if new_status == "opened":
        email.status = OutreachEmailStatus.opened
        email.opened_at = email.opened_at or now
    elif new_status == "clicked":
        email.status = OutreachEmailStatus.clicked
        email.clicked_at = email.clicked_at or now
        email.opened_at = email.opened_at or now
    elif new_status == "replied":
        email.status = OutreachEmailStatus.replied
        email.replied_at = now
        email.opened_at = email.opened_at or now
    elif new_status == "bounced":
        email.status = OutreachEmailStatus.bounced
    else:
        raise HTTPException(400, f"Invalid status: {new_status}")

    db.commit()
    return {"status": "updated", "email_id": email_id, "new_status": new_status}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_eligible_leads(db: Session, data: SendEmailsRequest):
    """Find leads eligible for outreach: score < threshold + has email + not yet emailed."""
    q = db.query(BusinessListing, ListingSEOCheck).join(
        ListingSEOCheck,
        ListingSEOCheck.business_listing_id == BusinessListing.id,
    ).filter(
        BusinessListing.email.isnot(None),
        BusinessListing.email != "",
        ListingSEOCheck.status == SEOCheckStatus.done,
        ListingSEOCheck.overall_score < data.max_score,
    )

    if data.search_query_id:
        q = q.filter(BusinessListing.search_query_id == data.search_query_id)
    if data.category:
        q = q.filter(BusinessListing.category.ilike(f"%{data.category}%"))
    if data.city:
        q = q.filter(BusinessListing.city.ilike(f"%{data.city}%"))

    # Exclude already emailed
    already_emailed = db.query(OutreachEmail.business_listing_id).filter(
        OutreachEmail.status != OutreachEmailStatus.bounced,
    ).subquery()
    q = q.filter(~BusinessListing.id.in_(already_emailed))

    return q.limit(data.limit).all()


def _normalize_recipient_email(raw_email: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return normalized email or an error string if invalid."""
    if not raw_email or not raw_email.strip():
        return None, "missing recipient email"

    candidate = raw_email.strip()
    try:
        normalized = validate_email(candidate, check_deliverability=False).normalized
        return normalized, None
    except EmailNotValidError as e:
        return None, str(e)


@router.post("/test-email")
def test_email(
    to_email: str = "kaimsardarii11@gmail.com",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Send a test outreach email to verify email configuration works."""
    if not settings.SENDGRID_API_KEY and not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        raise HTTPException(400, "No email provider configured. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD in .env")

    normalized_to_email, email_error = _normalize_recipient_email(to_email)
    if email_error:
        raise HTTPException(400, f"Invalid recipient email: {email_error}")

    dummy_problems = [
        "No SSL certificate — your site shows as 'Not Secure' in browsers",
        "Missing meta description — you are missing the chance to attract clicks from Google",
        "No robots.txt file — search engines do not know how to crawl your site",
        "Page loads in 5.2s (should be under 3s) — slow sites lose 53% of visitors",
        "No Local Business schema — missing rich results in Google Search",
    ]
    email_data = generate_email(
        business_name="Test Coffee Shop",
        website="testcoffeeshop.com.au",
        city="Melbourne",
        seo_score=35,
        problems=dummy_problems,
        from_name=settings.OUTREACH_FROM_NAME,
        category="Cafe",
        rating=4.2,
        reviews_count=312,
    )

    # Save first so tracking can update this exact row.
    outreach = OutreachEmail(
        to_email=to_email,
        subject=email_data["subject"],
        body_html=email_data["body_html"],
        status=OutreachEmailStatus.draft,
    )
    db.add(outreach)
    db.flush()

    # Inject open/click tracking into the outgoing body.
    body_to_send = email_data["body_html"]
    if settings.TRACKING_BASE_URL:
        body_to_send = inject_tracking(body_to_send, outreach.id, settings.TRACKING_BASE_URL)
        outreach.body_html = body_to_send

    message_id = send_email(
        to_email=normalized_to_email,
        subject=email_data["subject"],
        body_html=body_to_send,
    )

    if message_id:
        outreach.status = OutreachEmailStatus.sent
        outreach.sendgrid_message_id = message_id
        outreach.sent_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "status": "sent",
            "to": normalized_to_email,
            "subject": email_data["subject"],
            "message_id": message_id,
            "provider": "sendgrid" if settings.SENDGRID_API_KEY else "smtp",
            "mode": "ai" if settings.ANTHROPIC_API_KEY else "template",
            "outreach_email_id": outreach.id,
            "tracking_pixel_url": (
                f"{settings.TRACKING_BASE_URL}/track/open/{outreach.id}"
                if settings.TRACKING_BASE_URL else None
            ),
        }
    else:
        db.rollback()
        raise HTTPException(500, "Email sending failed. Check your SMTP settings and terminal logs.")


@router.post("/test-ai-email")
def test_ai_email(
    to_email: str = "kaimsardarii11@gmail.com",
    business_name: str = "Mike's Plumbing Sydney",
    website: str = "mikesplumbingsydney.com.au",
    city: str = "Sydney",
    category: str = "Plumber",
    seo_score: int = 38,
    rating: float = 4.6,
    reviews_count: int = 183,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Generate and send ONE AI-only email for a test business.
    Saves to DB so open/click tracking works exactly like real outreach emails.
    """
    if not settings.SENDGRID_API_KEY and not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        raise HTTPException(400, "No email provider configured. Set SMTP or SENDGRID in .env")

    normalized_to_email, email_error = _normalize_recipient_email(to_email)
    if email_error:
        raise HTTPException(400, f"Invalid recipient email: {email_error}")

    if not settings.ANTHROPIC_API_KEY and not settings.GROQ_API_KEY:
        raise HTTPException(400, "No AI key set. Add ANTHROPIC_API_KEY or GROQ_API_KEY to .env")

    if settings.ANTHROPIC_API_KEY:
        provider = f"Claude ({settings.AI_EMAIL_MODEL})"
    else:
        provider = f"Groq ({settings.GROQ_MODEL})"

    problems = [
        "No SSL certificate — site shows as 'Not Secure', critical for a trade business",
        "Page loads in 7.1s (should be under 3s) — losing emergency call leads",
        "Missing meta description — Google shows random text instead of your service info",
        "No Local Business schema — missing from Google Maps rich results",
        "No H1 tag — search engines can't identify your primary service keyword",
    ]

    # Generate AI email
    try:
        from app.services.maps.ai_email_generator import generate_ai_email
        email_data = generate_ai_email(
            business_name=business_name,
            website=website,
            city=city,
            category=category,
            seo_score=seo_score,
            problems=problems,
            from_name=settings.OUTREACH_FROM_NAME,
            rating=rating,
            reviews_count=reviews_count,
        )
    except Exception as e:
        raise HTTPException(500, f"AI generation failed — {type(e).__name__}: {e}")

    if not email_data:
        raise HTTPException(500, "AI returned empty result. Check your API key and quota.")

    # ── Save to DB first so we get an ID for tracking URLs ───────────────────
    outreach = OutreachEmail(
        to_email=to_email,
        subject=email_data["subject"],
        body_html=email_data["body_html"],
        status=OutreachEmailStatus.draft,
    )
    db.add(outreach)
    db.flush()  # get outreach.id

    # ── Inject tracking pixel and click tracking ──────────────────────────────
    body_to_send = email_data["body_html"]
    if settings.TRACKING_BASE_URL:
        body_to_send = inject_tracking(body_to_send, outreach.id, settings.TRACKING_BASE_URL)
        outreach.body_html = body_to_send
        logger.info(f"[TRACKING] Test email pixel injected → {settings.TRACKING_BASE_URL}/track/open/{outreach.id}")
    else:
        logger.warning("[TRACKING] TRACKING_BASE_URL not set — pixel NOT injected in test email.")

    # ── Send ──────────────────────────────────────────────────────────────────
    message_id = send_email(
        to_email=normalized_to_email,
        subject=email_data["subject"],
        body_html=body_to_send,
    )

    if not message_id:
        db.rollback()
        raise HTTPException(500, "Email sending failed. Check SMTP/SendGrid settings.")

    # ── Update DB record ──────────────────────────────────────────────────────
    outreach.status = OutreachEmailStatus.sent
    outreach.sendgrid_message_id = message_id
    outreach.sent_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "status": "sent",
        "to": normalized_to_email,
        "subject": email_data["subject"],
        "provider": provider,
        "message_id": message_id,
        "tracking_enabled": bool(settings.TRACKING_BASE_URL),
        "tracking_pixel_url": f"{settings.TRACKING_BASE_URL}/track/open/{outreach.id}" if settings.TRACKING_BASE_URL else None,
        "outreach_email_id": outreach.id,
        "business": {
            "name": business_name,
            "website": website,
            "city": city,
            "category": category,
            "seo_score": seo_score,
        },
    }


@router.post("/test-email-compare")
def test_email_compare(
    to_email: str = "kaimsardarii11@gmail.com",
    send: bool = False,
    # ── Customisable business fields (override the defaults from Swagger UI) ──
    business_name: str = "Mike's Plumbing Sydney",
    website: str = "mikesplumbingsydney.com.au",
    city: str = "Sydney",
    category: str = "Plumber",
    seo_score: int = 38,
    rating: float = 4.6,
    reviews_count: int = 183,
    current_user: User = Depends(require_admin),
):
    """
    Generate BOTH an AI email and a template email for the same business.

    - Returns both as JSON so you can compare side by side.
    - If send=true, also emails both versions to to_email so you see them in your inbox.
      (Template email first, then AI email with [AI] prefix on subject.)
    - Customise the business via query params: business_name, website, city, category,
      seo_score, rating, reviews_count — great for testing different business types.
    """
    dummy_business = {
        "business_name": business_name,
        "website": website,
        "city": city,
        "category": category,
        "seo_score": seo_score,
        "rating": rating,
        "reviews_count": reviews_count,
        "problems": [
            "No SSL certificate — site shows as 'Not Secure', critical for a trade business",
            "Page loads in 7.1s (should be under 3s) — losing emergency call leads",
            "Missing meta description — Google shows random text instead of your service info",
            "No Local Business schema — missing from Google Maps rich results",
            "No H1 tag — search engines can't identify your primary service keyword",
        ],
    }

    # ── 1. Force-generate TEMPLATE version (temporarily hide API key) ─────────
    from app.services.maps.outreach_email import _generate_template_email
    template_data = _generate_template_email(
        business_name=dummy_business["business_name"],
        website=dummy_business["website"],
        city=dummy_business["city"],
        seo_score=dummy_business["seo_score"],
        problems=dummy_business["problems"],
        from_name=settings.OUTREACH_FROM_NAME,
    )

    # ── 2. Generate AI version (Claude → Groq → none, auto-detected) ────────────
    ai_data = None
    ai_error = None
    ai_provider = None

    # Detect which provider is configured
    if settings.ANTHROPIC_API_KEY:
        ai_provider = f"Claude ({settings.AI_EMAIL_MODEL})"
    elif settings.GROQ_API_KEY:
        ai_provider = f"Groq ({settings.GROQ_MODEL})"

    if ai_provider:
        try:
            from app.services.maps.ai_email_generator import generate_ai_email
            ai_data = generate_ai_email(
                business_name=dummy_business["business_name"],
                website=dummy_business["website"],
                city=dummy_business["city"],
                category=dummy_business["category"],
                seo_score=dummy_business["seo_score"],
                problems=dummy_business["problems"],
                from_name=settings.OUTREACH_FROM_NAME,
                rating=dummy_business["rating"],
                reviews_count=dummy_business["reviews_count"],
            )
        except Exception as e:
            ai_error = f"{type(e).__name__}: {e}"
    else:
        ai_error = "No AI key set in .env — add ANTHROPIC_API_KEY (paid) or GROQ_API_KEY (free)"

    # ── 3. Optionally send both to inbox ──────────────────────────────────────
    sent_results = {}
    if send:
        if not settings.SENDGRID_API_KEY and not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
            raise HTTPException(400, "No email provider configured for sending")

        # Send template version
        tid = send_email(
            to_email=to_email,
            subject=f"[TEMPLATE] {template_data['subject']}",
            body_html=template_data["body_html"],
        )
        sent_results["template_message_id"] = tid

        # Send AI version if available
        if ai_data:
            import time
            time.sleep(2)  # small gap so they arrive in order
            aid = send_email(
                to_email=to_email,
                subject=f"[AI] {ai_data['subject']}",
                body_html=ai_data["body_html"],
            )
            sent_results["ai_message_id"] = aid

    return {
        "business_used": dummy_business,
        "template_email": {
            "subject": template_data["subject"],
            "body_html": template_data["body_html"],
        },
        "ai_email": {
            "subject": ai_data["subject"] if ai_data else None,
            "body_html": ai_data["body_html"] if ai_data else None,
            "error": ai_error,
            "available": ai_data is not None,
            "provider": ai_provider,
        },
        "sent_to_inbox": send,
        **sent_results,
    }
