"""
13-Point SEO Checker for Business Listings.
Runs comprehensive checks on business websites found via Google Maps.
"""
import re
import json
import time
import logging
import requests as req_lib
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 10


def run_seo_check(website: str, business_name: str = "", phone: str = "") -> dict:
    """Run 13-point SEO audit on a business website.

    Returns dict with all check results, score 0-100, and verdict.
    """
    result = {
        "overall_score": 0,
        "verdict": "Unreachable",
        # Technical
        "check_ssl": "fail",
        "check_robots": "fail",
        "check_sitemap": "fail",
        "check_canonical": "fail",
        "check_mobile": "fail",
        "check_speed": "fail",
        "load_time": None,
        # On-page
        "check_h1": "fail",
        "check_title": "fail",
        "title_text": "",
        "title_length": 0,
        "check_description": "fail",
        "description_text": "",
        "description_length": 0,
        "check_alt_tags": "fail",
        "images_total": 0,
        "images_missing_alt": 0,
        # Local SEO
        "check_business_name": "fail",
        "check_phone": "fail",
        "check_local_schema": "fail",
        "check_social_links": "fail",
        "check_contact_page": "fail",
    }

    url = website if website.startswith("http") else f"https://{website}"
    headers = {"User-Agent": USER_AGENT}

    # ─── Fetch the page ──────────────────────────────────────────────────
    html = None
    final_url = None
    start_time = time.time()

    for scheme_url in [url, url.replace("https://", "http://") if "https" in url else url]:
        try:
            resp = req_lib.get(scheme_url, headers=headers, timeout=TIMEOUT,
                               allow_redirects=True, verify=False)
            if resp.status_code == 200:
                html = resp.text
                final_url = resp.url
                break
        except Exception:
            continue

    load_time = round(time.time() - start_time, 2)
    result["load_time"] = load_time

    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    # ═══════════════════════════════════════════════════════════════════════
    # TECHNICAL CHECKS (35 points)
    # ═══════════════════════════════════════════════════════════════════════

    # 1. SSL/HTTPS (5 pts)
    result["check_ssl"] = "pass" if final_url and final_url.startswith("https") else "fail"

    # 2. Robots.txt (5 pts)
    try:
        base = f"{'https' if 'https' in final_url else 'http'}://{_get_domain(final_url)}"
        robots_resp = req_lib.get(f"{base}/robots.txt", headers=headers, timeout=5, verify=False)
        result["check_robots"] = "pass" if robots_resp.status_code == 200 and len(robots_resp.text) > 10 else "fail"
    except Exception:
        result["check_robots"] = "fail"

    # 3. Sitemap.xml (5 pts)
    try:
        sitemap_resp = req_lib.get(f"{base}/sitemap.xml", headers=headers, timeout=5, verify=False)
        result["check_sitemap"] = "pass" if sitemap_resp.status_code == 200 and "<?xml" in sitemap_resp.text[:200] else "fail"
    except Exception:
        result["check_sitemap"] = "fail"

    # 4. Canonical Tag (5 pts)
    canonical = soup.find("link", attrs={"rel": "canonical"})
    result["check_canonical"] = "pass" if canonical and canonical.get("href") else "fail"

    # 5. Mobile Responsive (5 pts)
    viewport = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
    result["check_mobile"] = "pass" if viewport else "fail"

    # 6. Page Speed (10 pts)
    if load_time <= 2.0:
        result["check_speed"] = "pass"
    elif load_time <= 4.0:
        result["check_speed"] = "warn"
    else:
        result["check_speed"] = "fail"

    # ═══════════════════════════════════════════════════════════════════════
    # ON-PAGE SEO CHECKS (40 points)
    # ═══════════════════════════════════════════════════════════════════════

    # 7. H1 Tag (10 pts) — exactly 1 H1 on homepage
    h1_tags = soup.find_all("h1")
    if len(h1_tags) == 1:
        result["check_h1"] = "pass"
    elif len(h1_tags) > 1:
        result["check_h1"] = "warn"
    else:
        result["check_h1"] = "fail"

    # 8. Meta Title (10 pts) — must be 50-60 characters
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""
    result["title_text"] = title[:255]
    result["title_length"] = len(title)
    if 50 <= len(title) <= 60:
        result["check_title"] = "pass"
    elif 30 <= len(title) < 50 or 60 < len(title) <= 80:
        result["check_title"] = "warn"
    else:
        result["check_title"] = "fail"

    # 9. Meta Description (10 pts) — must be 150-160 characters
    meta_desc = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    desc = (meta_desc.get("content") or "").strip() if meta_desc else ""
    result["description_text"] = desc[:500]
    result["description_length"] = len(desc)
    if 150 <= len(desc) <= 160:
        result["check_description"] = "pass"
    elif 100 <= len(desc) < 150 or 160 < len(desc) <= 200:
        result["check_description"] = "warn"
    else:
        result["check_description"] = "fail"

    # 10. Image Alt Tags (10 pts) — all images must have non-empty alt
    images = soup.find_all("img")
    result["images_total"] = len(images)
    missing_alt = 0
    for img in images:
        alt = img.get("alt", "")
        if not alt or not alt.strip():
            missing_alt += 1
    result["images_missing_alt"] = missing_alt
    if len(images) == 0:
        result["check_alt_tags"] = "warn"  # No images at all
    elif missing_alt == 0:
        result["check_alt_tags"] = "pass"
    elif missing_alt <= len(images) * 0.3:
        result["check_alt_tags"] = "warn"  # Less than 30% missing
    else:
        result["check_alt_tags"] = "fail"

    # ═══════════════════════════════════════════════════════════════════════
    # LOCAL SEO CHECKS (25 points)
    # ═══════════════════════════════════════════════════════════════════════

    body_text = soup.get_text().lower() if soup.find("body") else ""

    # 11. Business Name on Site (5 pts)
    if business_name:
        name_lower = business_name.lower().strip()
        # Check if business name appears on the page
        result["check_business_name"] = "pass" if name_lower in body_text else "fail"
    else:
        result["check_business_name"] = "warn"

    # 12. Phone Number on Site (5 pts)
    if phone:
        # Normalize phone: remove spaces, dashes, brackets
        phone_digits = re.sub(r'\D', '', phone)
        page_digits = re.sub(r'\D', '', body_text)
        result["check_phone"] = "pass" if phone_digits and phone_digits in page_digits else "fail"
    else:
        # Check if any phone-like pattern exists
        phone_pattern = re.search(r'(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}', body_text)
        result["check_phone"] = "warn" if phone_pattern else "fail"

    # 13. Local Business Schema (5 pts)
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    has_local_schema = False
    for script in scripts:
        try:
            data = json.loads(script.string or "")
            schema_type = data.get("@type", "")
            if isinstance(schema_type, list):
                schema_type = " ".join(schema_type)
            if any(t in schema_type for t in ["LocalBusiness", "Organization", "Store",
                                                "Restaurant", "Dentist", "MedicalBusiness",
                                                "ProfessionalService"]):
                has_local_schema = True
                break
        except (json.JSONDecodeError, AttributeError):
            continue
    result["check_local_schema"] = "pass" if has_local_schema else "fail"

    # 14. Social Media Links (5 pts)
    social_domains = ["facebook.com", "instagram.com", "linkedin.com",
                      "twitter.com", "x.com", "youtube.com"]
    social_found = 0
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        for sd in social_domains:
            if sd in href:
                social_found += 1
                break
    if social_found >= 3:
        result["check_social_links"] = "pass"
    elif social_found >= 1:
        result["check_social_links"] = "warn"
    else:
        result["check_social_links"] = "fail"

    # 15. Contact Page (5 pts)
    contact_found = False
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text().lower()
        if "contact" in href or "contact" in text:
            contact_found = True
            break
    result["check_contact_page"] = "pass" if contact_found else "fail"

    # ═══════════════════════════════════════════════════════════════════════
    # CALCULATE SCORE
    # ═══════════════════════════════════════════════════════════════════════

    score = 0

    # Technical (35 pts)
    score += _pts(result["check_ssl"], 5)
    score += _pts(result["check_robots"], 5)
    score += _pts(result["check_sitemap"], 5)
    score += _pts(result["check_canonical"], 5)
    score += _pts(result["check_mobile"], 5)
    score += _pts(result["check_speed"], 10)

    # On-page (40 pts)
    score += _pts(result["check_h1"], 10)
    score += _pts(result["check_title"], 10)
    score += _pts(result["check_description"], 10)
    score += _pts(result["check_alt_tags"], 10)

    # Local SEO (25 pts)
    score += _pts(result["check_business_name"], 5)
    score += _pts(result["check_phone"], 5)
    score += _pts(result["check_local_schema"], 5)
    score += _pts(result["check_social_links"], 5)
    score += _pts(result["check_contact_page"], 5)

    result["overall_score"] = score

    if score >= 70:
        result["verdict"] = "Good"
    elif score >= 50:
        result["verdict"] = "Needs Improvement"
    elif score >= 30:
        result["verdict"] = "Poor SEO"
    else:
        result["verdict"] = "SEO Required"

    return result


def _pts(check_value: str, max_pts: int) -> int:
    if check_value == "pass":
        return max_pts
    elif check_value == "warn":
        return max_pts // 2
    return 0


def _get_domain(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc or parsed.path.split("/")[0]
