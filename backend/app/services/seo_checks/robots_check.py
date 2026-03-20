"""
Robots.txt Check
================
Checks if robots.txt exists, is valid, and doesn't block everything.
Score: 0-100
"""

import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(8.0, connect=5.0)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}


async def check_robots(domain: str) -> dict[str, Any]:
    result = {
        "score": 0,
        "exists": False,
        "is_valid": False,
        "blocks_all": False,
        "has_sitemap_reference": False,
        "content_preview": None,
        "errors": [],
    }

    url = f"https://{domain}/robots.txt"
    fallback = f"http://{domain}/robots.txt"

    content = None
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=HEADERS,
        follow_redirects=True, verify=False
    ) as client:
        for target_url in (url, fallback):
            try:
                resp = await client.get(target_url)
                if resp.status_code == 200:
                    content = resp.text
                    break
            except Exception as e:
                result["errors"].append(str(e)[:80])

    if not content:
        result["errors"].append("robots.txt not found or unreachable")
        return result

    result["exists"] = True
    result["content_preview"] = content[:500]

    lines = [l.strip() for l in content.splitlines() if l.strip()]

    # Basic validity — should have at least one User-agent line
    has_user_agent = any(l.lower().startswith("user-agent") for l in lines)
    result["is_valid"] = has_user_agent

    # Check if ALL bots are blocked (Disallow: /)
    disallow_all = False
    current_agent = None
    for line in lines:
        lower = line.lower()
        if lower.startswith("user-agent:"):
            current_agent = line.split(":", 1)[1].strip()
        elif lower.startswith("disallow:") and current_agent == "*":
            value = line.split(":", 1)[1].strip()
            if value == "/":
                disallow_all = True

    result["blocks_all"] = disallow_all

    # Sitemap reference
    result["has_sitemap_reference"] = any(
        l.lower().startswith("sitemap:") for l in lines
    )

    # ── Score ─────────────────────────────────────────────────────────────────
    score = 0
    if result["exists"]:
        score += 40
    if result["is_valid"]:
        score += 30
    if not result["blocks_all"]:
        score += 20
    if result["has_sitemap_reference"]:
        score += 10

    result["score"] = min(score, 100)
    return result
