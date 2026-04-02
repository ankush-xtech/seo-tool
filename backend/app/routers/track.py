"""
Email tracking endpoints — no authentication required (clients hit these).

GET /track/open/{email_id}   → returns 1×1 transparent GIF, marks email as opened
GET /track/click/{email_id}  → redirect helper only (no click status tracking)
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import OutreachEmail, OutreachEmailStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/track", tags=["Tracking"])

# 1×1 transparent GIF (binary literal — smallest valid GIF)
_PIXEL_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00"
    b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)

_PIXEL_HEADERS = {
    # Reduce proxy/client caching so first real open is more likely to hit backend.
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, private",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.get("/debug")
def track_debug(db: Session = Depends(get_db)):
    """
    Public debug endpoint — no auth needed.
    Call this from your browser to confirm:
      1. ngrok is forwarding to your backend
      2. The /track router is registered correctly
      3. DB connection works
    URL: https://your-ngrok-url.ngrok-free.app/track/debug
    """
    from app.core.config import settings

    # Count emails + check last 5 for pixel presence
    total_emails = db.query(OutreachEmail).count()
    last_5 = (
        db.query(OutreachEmail)
        .order_by(OutreachEmail.id.desc())
        .limit(5)
        .all()
    )

    emails_info = []
    for e in last_5:
        base = settings.TRACKING_BASE_URL or ""
        pixel_injected = f"/track/open/{e.id}" in (e.body_html or "")
        emails_info.append({
            "id": e.id,
            "to": e.to_email,
            "status": e.status.value if e.status else None,
            "opened_at": str(e.opened_at) if e.opened_at else None,
            "clicked_at": str(e.clicked_at) if e.clicked_at else None,
            "pixel_injected_in_body": pixel_injected,
            "pixel_url": f"{base}/track/open/{e.id}" if base else "TRACKING_BASE_URL not set",
        })

    return {
        "status": "✅ Track router is reachable",
        "tracking_base_url": settings.TRACKING_BASE_URL or "❌ NOT SET in .env",
        "tracking_enabled": bool(settings.TRACKING_BASE_URL),
        "db_connection": "✅ OK",
        "total_outreach_emails_in_db": total_emails,
        "last_5_emails": emails_info,
        "instructions": {
            "step1": "Check tracking_base_url matches your current ngrok URL",
            "step2": "Check pixel_injected_in_body=true for the email you sent",
            "step3": "Open that email in Gmail, then refresh this page — opened_at should fill in",
            "step4": "If pixel_injected_in_body=false, restart backend and send a NEW email",
        },
    }


@router.api_route("/open/{email_id}", methods=["GET", "HEAD"], include_in_schema=False)
def track_open(email_id: int, request: Request, db: Session = Depends(get_db)):
    """Record that the client opened this email, then return a 1×1 transparent pixel."""
    try:
        email = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
        if email and not email.opened_at:
            now = datetime.now(timezone.utc)
            email.opened_at = now
            # Only upgrade status — never downgrade (e.g. clicked/replied should stay as-is).
            if email.status in (OutreachEmailStatus.draft, OutreachEmailStatus.sent):
                email.status = OutreachEmailStatus.opened
            db.commit()
            logger.info(
                f"Email {email_id} opened by {email.to_email} "
                f"method={request.method} ua={request.headers.get('user-agent', '-')[:180]}"
            )
    except Exception as e:
        logger.warning(f"track_open error for email {email_id}: {e}")

    if request.method == "HEAD":
        return Response(status_code=200, media_type="image/gif", headers=_PIXEL_HEADERS)
    return Response(content=_PIXEL_GIF, media_type="image/gif", headers=_PIXEL_HEADERS)


@router.get("/click/{email_id}", include_in_schema=False)
def track_click(email_id: int, to: str = "", db: Session = Depends(get_db)):
    """Record link click → set clicked_at + upgrade status, then redirect to original URL."""
    redirect_url = to or "https://www.google.com"

    try:
        email = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
        if email:
            now = datetime.now(timezone.utc)
            changed = False
            # Also mark as opened if pixel never fired
            if not email.opened_at:
                email.opened_at = now
                changed = True
            # Record the click
            if not email.clicked_at:
                email.clicked_at = now
                changed = True
            # Upgrade status: sent/opened → clicked  (never downgrade from replied/bounced)
            if email.status in (
                OutreachEmailStatus.draft,
                OutreachEmailStatus.sent,
                OutreachEmailStatus.opened,
            ):
                email.status = OutreachEmailStatus.clicked
                changed = True
            if changed:
                db.commit()
                logger.info(f"Email {email_id} link clicked by {email.to_email} → {redirect_url}")
    except Exception as e:
        logger.warning(f"track_click error for email {email_id}: {e}")

    return RedirectResponse(url=redirect_url, status_code=302)
