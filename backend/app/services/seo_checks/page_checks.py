"""
Mobile Check
============
Checks viewport meta tag and mobile-friendliness signals.
Score: 0-100
"""

import logging
from typing import Any
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}


async def check_mobile(domain: str) -> dict[str, Any]:
    result = {
        "score": 0,
        "has_viewport": False,
        "viewport_content": None,
        "has_responsive_meta": False,
        "errors": [],
    }

    html = await _fetch_html(domain)
    if not html:
        result["errors"].append("Could not fetch HTML")
        return result

    try:
        soup = BeautifulSoup(html, "lxml")

        viewport = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "viewport"})
        if viewport:
            result["has_viewport"] = True
            content = viewport.get("content", "")
            result["viewport_content"] = content[:200]
            result["has_responsive_meta"] = (
                "width=device-width" in content.lower()
            )

    except Exception as e:
        result["errors"].append(str(e)[:100])

    score = 0
    if result["has_viewport"]:
        score += 60
    if result["has_responsive_meta"]:
        score += 40

    result["score"] = min(score, 100)
    return result


async def check_social_meta(domain: str) -> dict[str, Any]:
    """
    Check Open Graph and Twitter Card meta tags.
    Score: 0-100
    """
    result = {
        "score": 0,
        "has_og_title": False,
        "has_og_description": False,
        "has_og_image": False,
        "has_twitter_card": False,
        "og_title": None,
        "og_description": None,
        "og_image": None,
        "twitter_card": None,
        "errors": [],
    }

    html = await _fetch_html(domain)
    if not html:
        result["errors"].append("Could not fetch HTML")
        return result

    try:
        soup = BeautifulSoup(html, "lxml")

        def get_meta(prop_name: str, attr: str = "property") -> str | None:
            tag = soup.find("meta", attrs={attr: prop_name})
            if tag and tag.get("content"):
                return tag["content"].strip()[:300]
            return None

        og_title = get_meta("og:title")
        og_desc = get_meta("og:description")
        og_image = get_meta("og:image")
        tw_card = get_meta("twitter:card") or get_meta("twitter:card", attr="name")

        result["has_og_title"] = bool(og_title)
        result["has_og_description"] = bool(og_desc)
        result["has_og_image"] = bool(og_image)
        result["has_twitter_card"] = bool(tw_card)
        result["og_title"] = og_title
        result["og_description"] = og_desc
        result["og_image"] = og_image
        result["twitter_card"] = tw_card

    except Exception as e:
        result["errors"].append(str(e)[:100])

    score = 0
    if result["has_og_title"]:
        score += 30
    if result["has_og_description"]:
        score += 25
    if result["has_og_image"]:
        score += 25
    if result["has_twitter_card"]:
        score += 20

    result["score"] = min(score, 100)
    return result


async def check_headings(domain: str) -> dict[str, Any]:
    """
    Check heading structure (H1-H3).
    Score: 0-100
    """
    result = {
        "score": 0,
        "h1_count": 0,
        "h2_count": 0,
        "h3_count": 0,
        "has_single_h1": False,
        "h1_text": None,
        "errors": [],
    }

    html = await _fetch_html(domain)
    if not html:
        result["errors"].append("Could not fetch HTML")
        return result

    try:
        soup = BeautifulSoup(html, "lxml")

        h1s = soup.find_all("h1")
        h2s = soup.find_all("h2")
        h3s = soup.find_all("h3")

        result["h1_count"] = len(h1s)
        result["h2_count"] = len(h2s)
        result["h3_count"] = len(h3s)
        result["has_single_h1"] = len(h1s) == 1

        if h1s:
            result["h1_text"] = h1s[0].get_text(strip=True)[:200]

    except Exception as e:
        result["errors"].append(str(e)[:100])

    score = 0
    if result["h1_count"] == 1:
        score += 50   # Exactly one H1 is ideal
    elif result["h1_count"] > 1:
        score += 20   # Multiple H1s — not ideal
    if result["h2_count"] > 0:
        score += 30
    if result["h3_count"] > 0:
        score += 20

    result["score"] = min(score, 100)
    return result


async def _fetch_html(domain: str) -> str | None:
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
