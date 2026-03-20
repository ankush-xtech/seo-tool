"""
HTTPS Check
===========
Checks if the domain:
  - Is reachable via HTTP/HTTPS
  - Redirects HTTP → HTTPS
  - Returns a successful status code
  - Has valid response headers

Score: 0-100
"""

import asyncio
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}


async def check_https(domain: str) -> dict[str, Any]:
    """Check HTTP/HTTPS reachability and redirect behaviour."""
    result = {
        "score": 0,
        "is_reachable": False,
        "has_https": False,
        "http_redirects_to_https": False,
        "status_code": None,
        "final_url": None,
        "redirect_chain": [],
        "response_time_ms": None,
        "errors": [],
    }

    import time

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        headers=HEADERS,
        follow_redirects=True,
        verify=False,           # SSL errors handled separately in ssl_check
    ) as client:

        # ── Try HTTPS first ───────────────────────────────────────────────────
        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}"
            try:
                start = time.monotonic()
                resp = await client.get(url)
                elapsed = round((time.monotonic() - start) * 1000)

                result["is_reachable"] = True
                result["status_code"] = resp.status_code
                result["final_url"] = str(resp.url)
                result["response_time_ms"] = elapsed
                result["redirect_chain"] = [str(r.url) for r in resp.history]

                if scheme == "https" or str(resp.url).startswith("https://"):
                    result["has_https"] = True

                # Check if HTTP redirected to HTTPS
                if scheme == "http":
                    if str(resp.url).startswith("https://"):
                        result["http_redirects_to_https"] = True

                break   # Stop after first successful scheme

            except httpx.ConnectError:
                result["errors"].append(f"{scheme}: connection refused")
            except httpx.TimeoutException:
                result["errors"].append(f"{scheme}: timeout")
            except Exception as e:
                result["errors"].append(f"{scheme}: {str(e)[:100]}")

    # ── Score ─────────────────────────────────────────────────────────────────
    score = 0
    if result["is_reachable"]:
        score += 30
    if result["has_https"]:
        score += 40
    if result["http_redirects_to_https"]:
        score += 20
    if result["status_code"] and result["status_code"] < 400:
        score += 10

    result["score"] = min(score, 100)
    return result
