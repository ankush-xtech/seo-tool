"""
Outreach Email Generator + SendGrid / SMTP Sender.

Email generation strategy:
  AI-ONLY — uses whichever key is configured:
    1. Anthropic (Claude)  — if ANTHROPIC_API_KEY is set in .env
    2. Groq (Llama)        — if GROQ_API_KEY is set in .env
  If neither key is present, an error is raised (no silent fallback to template).

Sending strategy (auto-selected at runtime):
  1. SendGrid   — if SENDGRID_API_KEY is set
  2. Gmail SMTP — if SMTP_HOST / SMTP_USER / SMTP_PASSWORD are set
"""
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def inject_tracking(html: str, email_id: int, base_url: str) -> str:
    """Inject open pixel and rewrite links to open-fallback redirect endpoint."""
    base_url = base_url.rstrip("/")
    tracking_prefix = f"{base_url}/track/"

    # ── Open-tracking pixel ───────────────────────────────────────────────────
    # Rules for reliable Gmail pixel tracking:
    #   • NO display:none / opacity:0 — Gmail skips loading invisible images
    #   • Must be INSIDE a container  — Gmail strips top-level floating elements
    #   • Place as first child of the outermost div so it loads before body content
    pixel = (
        f'<img src="{base_url}/track/open/{email_id}" '
        f'width="1" height="1" border="0" '
        f'style="width:1px;height:1px;border:0;margin:0;padding:0;" alt="">'
    )
    if "<body" in html:
        # Has a proper <body> tag — inject as first child
        html = re.sub(r"(<body[^>]*>)", rf"\1\n{pixel}", html, count=1)
    elif re.search(r"<div[^>]*>", html):
        # No <body> (typical AI / template email) — inject as FIRST CHILD
        # of the outermost <div> so the pixel is inside the container, not floating before it
        html = re.sub(r"(<div[^>]*>)", rf"\1\n{pixel}", html, count=1)
    else:
        html = pixel + "\n" + html

    # Rewrite links through /track/click so link clicks can still mark as opened
    # without storing a separate clicked status.
    def _wrap_link(m: re.Match) -> str:
        original_url = m.group(1)
        if original_url.startswith(("mailto:", "tel:", "#", tracking_prefix)):
            return m.group(0)
        target = original_url if "://" in original_url else f"https://{original_url}"
        encoded = urllib.parse.quote(target, safe="")
        return f'href="{base_url}/track/click/{email_id}?to={encoded}"'

    html = re.sub(r'href="([^"#][^"]*)"', _wrap_link, html)
    return html


def inject_preview_button(body_html: str, preview_url: str) -> str:
    """Inject a 'View Your Preview Website' CTA button into the email body.

    Inserts the button block before the sign-off paragraph
    ('Looking forward' or 'Best regards').
    """
    button_html = f"""
    <div style="text-align:center;margin:28px 0;">
        <p style="color:#2c3e50;margin-bottom:12px;font-size:14px;">
            We've also created a quick preview of what your improved website could look like:
        </p>
        <a href="{preview_url}" target="_blank"
           style="display:inline-block;background:linear-gradient(135deg,#2563eb,#0891b2);
                  color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:8px;
                  font-weight:600;font-size:15px;letter-spacing:0.3px;">
            🌐 View Your Preview Website
        </a>
        <p style="color:#95a5a6;font-size:11px;margin-top:8px;">
            This is a sample preview — your actual website can look even better!
        </p>
    </div>"""

    # Try to insert before "Looking forward" or "Best regards"
    for marker in ["Looking forward", "Best regards"]:
        pattern = f"(<p[^>]*>\\s*{marker})"
        if re.search(pattern, body_html, re.IGNORECASE):
            body_html = re.sub(
                pattern,
                f"{button_html}\n\\1",
                body_html,
                count=1,
                flags=re.IGNORECASE,
            )
            return body_html

    # Fallback: insert before the last closing </div>
    last_div = body_html.rfind("</div>")
    if last_div != -1:
        body_html = body_html[:last_div] + button_html + "\n" + body_html[last_div:]

    return body_html


def generate_email(
    business_name: str,
    website: str,
    city: str,
    seo_score: int,
    problems: list[str],
    from_name: str = "SEO Agency",
    category: str = "",
    rating: Optional[float] = None,
    reviews_count: Optional[int] = None,
) -> dict:
    """Generate a personalised outreach email using AI (Anthropic or Groq).

    Provider priority: Anthropic → Groq (auto-detected from .env keys).
    Raises RuntimeError if no AI key is configured or if generation fails.

    Returns {"subject": str, "body_html": str}
    """
    from app.core.config import settings

    # ── Guard: must have at least one AI key ─────────────────────────────
    if not settings.ANTHROPIC_API_KEY and not settings.GROQ_API_KEY:
        raise RuntimeError(
            "No AI provider configured. Add ANTHROPIC_API_KEY or GROQ_API_KEY to .env"
        )

    # ── Generate via AI (provider auto-detected inside generate_ai_email) ─
    
    
    ai_result = generate_ai_email(
        business_name=business_name,
        website=website,
        city=city,
        category=category,
        seo_score=seo_score,
        problems=problems,
        from_name=from_name,
        rating=rating,
        reviews_count=reviews_count,
    )
    if not ai_result:
        raise RuntimeError(f"AI email generation returned empty result for {business_name}")

    logger.info(f"AI-generated email ready for {business_name}")
    return ai_result


def _generate_template_email(
    business_name: str,
    website: str,
    city: str,
    seo_score: int,
    problems: list[str],
    from_name: str = "SEO Agency",
) -> dict:
    """
    Static HTML template email — no API key needed, always free.
    Uses fixed subject and Sparksview brand structure.
    """
    from app.core.config import settings

    # ── Static subject — same for every email ────────────────────────────────
    subject = settings.OUTREACH_SUBJECT

    # ── Build problems bullet list ────────────────────────────────────────────
    problems_html = ""
    for p in problems[:6]:
        problems_html += f'<li style="margin-bottom:8px;color:#2c3e50;">{p}</li>'

    body_html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#2c3e50;line-height:1.6;">

    <p>Hi there,</p>

    <p>We hope you're doing well.</p>

    <p>We are reaching out from <strong>{settings.COMPANY_NAME}</strong>, an {settings.COMPANY_TYPE}
    based in {settings.COMPANY_COUNTRY} specializing in {settings.COMPANY_SPECIALIZATION}.
    We recently conducted a basic audit of your website
    <a href="{website}" style="color:#2980b9;">{website}</a>
    and identified several important SEO-related issues that may be impacting
    your online visibility and performance, including:</p>

    <div style="background:#fdf2f2;border-left:4px solid #e74c3c;padding:14px 18px;margin:20px 0;border-radius:4px;">
        <ul style="margin:0;padding-left:20px;">
            {problems_html}
        </ul>
    </div>

    <p>There is absolutely no obligation — our goal is simply to provide valuable
    insights that can help you improve your website's performance.</p>

    <p>If you'd like us to share your personalized SEO audit report, just reply to
    this email, and we'll send it over.</p>

    <p>Looking forward to your response.</p>

    <p style="margin-top:28px;">
        Best regards,<br><br>
        <strong>{settings.COMPANY_NAME}</strong><br>
        📧 <a href="mailto:{settings.COMPANY_EMAIL}" style="color:#2980b9;">{settings.COMPANY_EMAIL}</a><br>
        🌐 <a href="{settings.COMPANY_WEBSITE}" style="color:#2980b9;">{settings.COMPANY_WEBSITE}</a>
    </p>

    <hr style="border:none;border-top:1px solid #ecf0f1;margin:28px 0;">
    <p style="font-size:11px;color:#95a5a6;">
        You are receiving this because your business was found on Google Maps.
        If you do not wish to receive further emails, simply reply with "unsubscribe".
    </p>

</div>"""

    return {"subject": subject, "body_html": body_html.strip()}


def get_seo_problems(check: dict) -> list[str]:
    """Convert SEO check results into human-readable problem list."""
    problems = []

    if check.get("check_ssl") == "fail":
        problems.append("No SSL certificate — your site shows as 'Not Secure' in browsers")
    if check.get("check_title") in ("fail", "warn"):
        length = check.get("title_length", 0)
        if length == 0:
            problems.append("Missing page title — Google cannot display your site properly in search results")
        else:
            problems.append(f"Page title is {length} characters (should be 50-60 for best results)")
    if check.get("check_description") in ("fail", "warn"):
        length = check.get("description_length", 0)
        if length == 0:
            problems.append("No meta description — you are missing the chance to attract clicks from Google")
        else:
            problems.append(f"Meta description is {length} characters (should be 150-160 for best results)")
    if check.get("check_h1") == "fail":
        problems.append("No H1 heading tag — Google needs this to understand your page topic")
    elif check.get("check_h1") == "warn":
        problems.append("Multiple H1 tags found — your homepage should have exactly one H1")
    if check.get("check_alt_tags") in ("fail", "warn"):
        missing = check.get("images_missing_alt", 0)
        total = check.get("images_total", 0)
        if missing > 0:
            problems.append(f"{missing} of {total} images have no alt text — hurting your Google Image rankings")
    if check.get("check_robots") == "fail":
        problems.append("No robots.txt file — search engines do not know how to crawl your site")
    if check.get("check_sitemap") == "fail":
        problems.append("No sitemap.xml — Google cannot efficiently discover all your pages")
    if check.get("check_mobile") == "fail":
        problems.append("Not mobile-friendly — over 60% of searches happen on phones")
    if check.get("check_speed") in ("fail", "warn"):
        load_time = check.get("load_time", 0)
        if load_time:
            problems.append(f"Page loads in {load_time}s (should be under 3s) — slow sites lose 53% of visitors")
    if check.get("check_canonical") == "fail":
        problems.append("No canonical tag — risk of duplicate content penalizing your rankings")
    if check.get("check_local_schema") == "fail":
        problems.append("No Local Business schema — missing rich results in Google Search")
    if check.get("check_social_links") == "fail":
        problems.append("No social media links found on your website")
    if check.get("check_contact_page") == "fail":
        problems.append("No contact page found — making it hard for customers to reach you")

    return problems


def send_email_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    body_html: str,
) -> Optional[str]:
    """Send email via SMTP (Gmail, Outlook, etc). Returns message_id on success."""
    import smtplib
    import uuid
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email

        # Generate a message ID for tracking
        message_id = str(uuid.uuid4())
        msg["Message-ID"] = f"<{message_id}@seo-outreach>"

        # Attach HTML body
        msg.attach(MIMEText(body_html, "html"))

        # Connect and send
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

        logger.info(f"Email sent via SMTP to {to_email}, message_id={message_id}")
        return message_id

    except Exception as e:
        logger.error(f"SMTP send failed to {to_email}: {e}")
        return None


def send_email_sendgrid(
    api_key: str,
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    body_html: str,
) -> Optional[str]:
    """Send email via SendGrid API. Returns message_id on success, None on failure."""
    import requests as req_lib

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [{"type": "text/html", "value": body_html}],
        # Disable SendGrid's built-in tracking — we inject our OWN pixel and
        # click-redirect URLs before sending, so SendGrid must NOT rewrite them.
        "tracking_settings": {
            "open_tracking": {"enable": False},
            "click_tracking": {"enable": False},
        },
    }

    try:
        resp = req_lib.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        if resp.status_code in (200, 201, 202):
            message_id = resp.headers.get("X-Message-Id")
            logger.info(f"Email sent to {to_email}, message_id={message_id}")
            return message_id
        else:
            logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
            return None

    except Exception as e:
        logger.error(f"SendGrid request failed: {e}")
        return None


def send_email(to_email: str, subject: str, body_html: str) -> Optional[str]:
    """Auto-select email provider: SendGrid if key exists, otherwise Gmail SMTP."""
    from app.core.config import settings

    from_email = settings.OUTREACH_FROM_EMAIL
    from_name = settings.OUTREACH_FROM_NAME

    # Try SendGrid first
    if settings.SENDGRID_API_KEY:
        return send_email_sendgrid(
            api_key=settings.SENDGRID_API_KEY,
            from_email=from_email, from_name=from_name,
            to_email=to_email, subject=subject, body_html=body_html,
        )

    # Fall back to SMTP (Gmail)
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
        return send_email_smtp(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
            from_email=from_email, from_name=from_name,
            to_email=to_email, subject=subject, body_html=body_html,
        )

    logger.error("No email provider configured. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD or SENDGRID_API_KEY in .env")
    return None
