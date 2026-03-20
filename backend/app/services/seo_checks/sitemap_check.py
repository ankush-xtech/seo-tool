"""
Sitemap Check
=============
Checks if sitemap.xml exists and is valid XML.
Score: 0-100
"""

import logging
from typing import Any
import httpx
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}

SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",
]


async def check_sitemap(domain: str) -> dict[str, Any]:
    result = {
        "score": 0,
        "exists": False,
        "is_valid_xml": False,
        "url_count": 0,
        "sitemap_url": None,
        "is_sitemap_index": False,
        "errors": [],
    }

    content = None
    found_url = None

    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=HEADERS,
        follow_redirects=True, verify=False
    ) as client:
        for path in SITEMAP_PATHS:
            for scheme in ("https", "http"):
                url = f"{scheme}://{domain}{path}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                        content = resp.text
                        found_url = url
                        break
                    elif resp.status_code == 200 and len(resp.text) > 100:
                        # Some servers don't set content-type correctly
                        if "<urlset" in resp.text or "<sitemapindex" in resp.text:
                            content = resp.text
                            found_url = url
                            break
                except Exception:
                    continue
            if content:
                break

    if not content:
        result["errors"].append("No sitemap found at common paths")
        return result

    result["exists"] = True
    result["sitemap_url"] = found_url

    # ── Parse XML ─────────────────────────────────────────────────────────────
    try:
        root = ET.fromstring(content)
        result["is_valid_xml"] = True

        # Detect sitemap index vs regular sitemap
        tag = root.tag.lower()
        if "sitemapindex" in tag:
            result["is_sitemap_index"] = True
            # Count child sitemaps
            result["url_count"] = len(list(root))
        else:
            # Count <url> entries
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = root.findall("sm:url", ns)
            if not urls:
                urls = root.findall("url")
            result["url_count"] = len(urls)

    except ET.ParseError as e:
        result["errors"].append(f"Invalid XML: {str(e)[:100]}")

    # ── Score ─────────────────────────────────────────────────────────────────
    score = 0
    if result["exists"]:
        score += 40
    if result["is_valid_xml"]:
        score += 40
    if result["url_count"] > 0:
        score += 20

    result["score"] = min(score, 100)
    return result
