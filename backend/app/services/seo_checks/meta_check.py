"""
Meta Tags Check
===============
Checks title tag and meta description — presence, length, quality.
Score: 0-100
"""

import logging
from typing import Any
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}

TITLE_MIN = 30
TITLE_MAX = 60
DESC_MIN = 120
DESC_MAX = 160


async def check_meta(domain: str) -> dict[str, Any]:
    """Check title and meta description tags."""
    result = {
        "score": 0,
        "has_title": False,
        "title": None,
        "title_length": 0,
        "title_ok_length": False,
        "has_description": False,
        "description": None,
        "description_length": 0,
        "description_ok_length": False,
        "has_canonical": False,
        "canonical_url": None,
        "has_viewport": False,
        "errors": [],
    }

    html = await _fetch_html(domain)
    if not html:
        result["errors"].append("Could not fetch page HTML")
        return result

    try:
        soup = BeautifulSoup(html, "lxml")

        # ── Title ─────────────────────────────────────────────────────────────
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
            result["has_title"] = True
            result["title"] = title[:200]
            result["title_length"] = len(title)
            result["title_ok_length"] = TITLE_MIN <= len(title) <= TITLE_MAX

        # ── Meta description ──────────────────────────────────────────────────
        desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        if desc_tag and desc_tag.get("content"):
            desc = desc_tag["content"].strip()
            result["has_description"] = True
            result["description"] = desc[:300]
            result["description_length"] = len(desc)
            result["description_ok_length"] = DESC_MIN <= len(desc) <= DESC_MAX

        # ── Canonical ─────────────────────────────────────────────────────────
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            result["has_canonical"] = True
            result["canonical_url"] = canonical["href"][:200]

        # ── Viewport ─────────────────────────────────────────────────────────
        viewport = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "viewport"})
        if viewport:
            result["has_viewport"] = True

    except Exception as e:
        result["errors"].append(f"Parse error: {str(e)[:100]}")

    # ── Score ─────────────────────────────────────────────────────────────────
    score = 0
    if result["has_title"]:
        score += 30
        if result["title_ok_length"]:
            score += 15
    if result["has_description"]:
        score += 30
        if result["description_ok_length"]:
            score += 15
    if result["has_canonical"]:
        score += 5
    if result["has_viewport"]:
        score += 5

    result["score"] = min(score, 100)
    return result


async def _fetch_html(domain: str) -> str | None:
    """Fetch the homepage HTML. Try HTTPS first, fallback to HTTP."""
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=HEADERS,
        follow_redirects=True, verify=False
    ) as client:
        for scheme in ("https", "http"):
            try:
                resp = await client.get(f"{scheme}://{domain}")
                if resp.status_code < 400:
                    return resp.text
            except Exception:
                continue
    return None
