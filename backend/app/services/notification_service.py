"""
Notification Service
====================
Handles:
  - Creating in-app notifications
  - Listing / marking read
  - Evaluating alert rules against domain check results
  - Sending email alerts (SMTP)
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import (
    Notification, NotificationStatus, AlertRule, AlertCondition,
    Domain, User, SEOResult
)
from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Create notification ──────────────────────────────────────────────────────

def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    meta: dict = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        meta=meta or {},
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


# ─── List notifications ───────────────────────────────────────────────────────

def get_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.status == NotificationStatus.unread)

    total = query.count()
    items = query.order_by(Notification.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    unread_count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user_id,
        Notification.status == NotificationStatus.unread,
    ).scalar() or 0

    return {
        "notifications": items,
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "per_page": per_page,
    }


def mark_read(db: Session, user_id: int, notification_id: Optional[int] = None) -> int:
    """Mark one or all notifications as read. Returns count updated."""
    query = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.status == NotificationStatus.unread,
    )
    if notification_id:
        query = query.filter(Notification.id == notification_id)

    count = query.update({"status": NotificationStatus.read})
    db.commit()
    return count


def get_unread_count(db: Session, user_id: int) -> int:
    return db.query(func.count(Notification.id)).filter(
        Notification.user_id == user_id,
        Notification.status == NotificationStatus.unread,
    ).scalar() or 0


# ─── Alert rule evaluation ────────────────────────────────────────────────────

def evaluate_alert_rules(db: Session, domain: Domain, new_score: float) -> None:
    """
    Called after a domain SEO check completes.
    Checks all active alert rules against the new score.
    Creates notifications (and optionally sends email) for matching rules.
    """
    if new_score is None:
        return

    # Get previous score for score_drop check
    prev_result = (
        db.query(SEOResult.overall_score)
        .filter(SEOResult.domain_id == domain.id)
        .order_by(SEOResult.checked_at.desc())
        .offset(1)   # Skip the latest (just stored), get the one before
        .first()
    )
    prev_score = float(prev_result[0]) if prev_result and prev_result[0] else None

    # Get all active alert rules
    rules = db.query(AlertRule).filter(AlertRule.is_active == True).all()

    for rule in rules:
        # Apply TLD filter if set
        if rule.tld_filter and domain.tld != rule.tld_filter.lower().strip("."):
            continue

        triggered = False
        trigger_message = ""

        if rule.condition == AlertCondition.score_above:
            if rule.threshold is not None and new_score >= rule.threshold:
                triggered = True
                trigger_message = f"{domain.name} scored {new_score} (above threshold {rule.threshold})"

        elif rule.condition == AlertCondition.score_below:
            if rule.threshold is not None and new_score < rule.threshold:
                triggered = True
                trigger_message = f"{domain.name} scored {new_score} (below threshold {rule.threshold})"

        elif rule.condition == AlertCondition.score_drop:
            if prev_score is not None and rule.threshold is not None:
                drop = prev_score - new_score
                if drop >= rule.threshold:
                    triggered = True
                    trigger_message = (
                        f"{domain.name} score dropped by {round(drop, 1)} points "
                        f"({round(prev_score,1)} → {new_score})"
                    )

        elif rule.condition == AlertCondition.check_failed:
            if domain.check_status and str(domain.check_status) == "failed":
                triggered = True
                trigger_message = f"SEO check failed for {domain.name}"

        if triggered:
            # Create in-app notification
            user = db.query(User).filter(User.id == rule.user_id).first()
            if user:
                create_notification(
                    db=db,
                    user_id=rule.user_id,
                    title=f"Alert: {rule.name}",
                    message=trigger_message,
                    meta={"domain": domain.name, "score": new_score, "rule_id": rule.id},
                )
                logger.info(f"[Alert] Rule '{rule.name}' triggered for {domain.name}")

                # Send email if configured
                if rule.email_notify and user.email:
                    _send_alert_email(user.email, user.full_name, rule.name, trigger_message)


# ─── Email sending ────────────────────────────────────────────────────────────

def _send_alert_email(to_email: str, to_name: str, rule_name: str, message: str) -> bool:
    """Send alert email via SMTP. Returns True on success."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.debug("[Email] SMTP not configured — skipping email alert")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"SEO Alert: {rule_name}"
        msg["From"] = settings.EMAILS_FROM
        msg["To"] = to_email

        html = f"""
        <html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;padding:20px">
          <h2 style="color:#4f7cf8">SEO Alert Triggered</h2>
          <p>Hi {to_name},</p>
          <p>Your alert rule <strong>{rule_name}</strong> was triggered:</p>
          <div style="background:#f5f5f5;padding:14px;border-radius:8px;border-left:4px solid #4f7cf8;margin:16px 0">
            {message}
          </div>
          <p>Login to your dashboard to view details.</p>
          <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
          <p style="color:#999;font-size:12px">SEO Automation Tool — You can manage your alerts in Settings.</p>
        </body></html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM, to_email, msg.as_string())

        logger.info(f"[Email] Alert email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"[Email] Failed to send alert email: {e}")
        return False


def send_digest_email(to_email: str, to_name: str, stats: dict) -> bool:
    """Send daily/weekly digest email with domain stats."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"SEO Daily Digest — {stats.get('date', 'Today')}"
        msg["From"] = settings.EMAILS_FROM
        msg["To"] = to_email

        rows = ""
        for tld in stats.get("top_tlds", [])[:5]:
            rows += f"<tr><td style='padding:6px 10px'>.{tld['tld']}</td><td style='padding:6px 10px'>{tld['count']}</td></tr>"

        html = f"""
        <html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;padding:20px">
          <h2 style="color:#4f7cf8">Daily SEO Digest</h2>
          <p>Hi {to_name}, here's your summary for {stats.get('date', 'today')}:</p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <tr style="background:#f5f5f5">
              <td style="padding:8px 10px;font-weight:600">Metric</td>
              <td style="padding:8px 10px;font-weight:600">Value</td>
            </tr>
            <tr><td style='padding:6px 10px'>Domains fetched today</td><td style='padding:6px 10px'><strong>{stats.get('fetched_today', 0)}</strong></td></tr>
            <tr style="background:#fafafa"><td style='padding:6px 10px'>Total domains</td><td style='padding:6px 10px'>{stats.get('total_domains', 0)}</td></tr>
            <tr><td style='padding:6px 10px'>SEO checked</td><td style='padding:6px 10px'>{stats.get('checked', 0)}</td></tr>
            <tr style="background:#fafafa"><td style='padding:6px 10px'>Avg SEO score</td><td style='padding:6px 10px'>{stats.get('avg_seo_score') or '—'}</td></tr>
          </table>
          <h4>Top TLDs today</h4>
          <table style="width:100%;border-collapse:collapse">
            <tr style="background:#f5f5f5">
              <td style="padding:6px 10px;font-weight:600">TLD</td>
              <td style="padding:6px 10px;font-weight:600">Count</td>
            </tr>
            {rows}
          </table>
          <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
          <p style="color:#999;font-size:12px">SEO Automation Tool — Manage digest settings in your profile.</p>
        </body></html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM, to_email, msg.as_string())

        return True
    except Exception as e:
        logger.error(f"[Email] Digest email failed: {e}")
        return False
