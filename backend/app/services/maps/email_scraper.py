"""
Scrape business websites to extract email and phone contact info.
Reuses patterns from the SEO check in fetch.py.
"""
import re
import logging
import requests as req_lib

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)
PHONE_AU_RE = re.compile(
    r'(?:\+61|0)\s*[2-478](?:\s*\d){8}|'   # landline / mobile
    r'(?:\+61|0)\s*1[38]00(?:\s*\d){6}',    # 1300/1800
    re.IGNORECASE,
)
IGNORED_EMAIL_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "googleapis.com",
    "w3.org", "schema.org", "facebook.com", "twitter.com",
    "google.com", "gstatic.com", "gravatar.com", "wordpress.org",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]
_ua_idx = 0


def _next_ua() -> str:
    global _ua_idx
    ua = USER_AGENTS[_ua_idx % len(USER_AGENTS)]
    _ua_idx += 1
    return ua


def scrape_contact_info(website_url: str, timeout: float = 8.0) -> dict:
    """Visit a business website and extract email + phone.

    Returns {"email": str|None, "phone": str|None}
    """
    email = None
    phone = None

    if not website_url:
        return {"email": None, "phone": None}

    # Ensure URL has scheme
    url = website_url
    if not url.startswith("http"):
        url = f"https://{url}"

    try:
        resp = req_lib.get(
            url,
            timeout=timeout,
            headers={"User-Agent": _next_ua()},
            allow_redirects=True,
            verify=False,
        )
        html = resp.text[:200_000]  # Limit to 200KB to avoid memory issues

        # Extract emails
        emails = EMAIL_RE.findall(html)
        for e in emails:
            domain = e.split("@")[1].lower()
            if domain not in IGNORED_EMAIL_DOMAINS and not e.endswith(".png") and not e.endswith(".jpg"):
                email = e.lower()
                break

        # Extract Australian phone numbers
        phones = PHONE_AU_RE.findall(html)
        if phones:
            # Clean up: remove extra spaces
            phone = re.sub(r'\s+', ' ', phones[0]).strip()

        # Also check for mailto: links
        if not email:
            mailto = re.findall(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html)
            for e in mailto:
                domain = e.split("@")[1].lower()
                if domain not in IGNORED_EMAIL_DOMAINS:
                    email = e.lower()
                    break

        # Check contact page if no email found on homepage
        if not email and "/contact" not in url.lower():
            email, phone2 = _try_contact_page(url, timeout)
            if not phone and phone2:
                phone = phone2

    except Exception as e:
        logger.debug(f"Failed to scrape {website_url}: {e}")

    return {"email": email, "phone": phone}


def _try_contact_page(base_url: str, timeout: float) -> tuple:
    """Try to find and scrape a /contact page."""
    from urllib.parse import urljoin
    contact_paths = ["/contact", "/contact-us", "/about/contact"]

    for path in contact_paths:
        try:
            url = urljoin(base_url, path)
            resp = req_lib.get(
                url, timeout=timeout,
                headers={"User-Agent": _next_ua()},
                allow_redirects=True, verify=False,
            )
            if resp.status_code != 200:
                continue

            html = resp.text[:200_000]
            emails = EMAIL_RE.findall(html)
            email = None
            for e in emails:
                domain = e.split("@")[1].lower()
                if domain not in IGNORED_EMAIL_DOMAINS:
                    email = e.lower()
                    break

            phones = PHONE_AU_RE.findall(html)
            phone = re.sub(r'\s+', ' ', phones[0]).strip() if phones else None

            if email or phone:
                return email, phone
        except Exception:
            continue

    return None, None
