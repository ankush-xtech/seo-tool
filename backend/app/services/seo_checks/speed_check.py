"""
Speed Check
===========
Measures page load response time and page size.
Score: 0-100 (faster = higher score)
"""

import time
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}


async def check_speed(domain: str) -> dict[str, Any]:
    result = {
        "score": 0,
        "response_time_ms": None,
        "page_size_kb": None,
        "is_fast": False,        # < 1000ms
        "is_acceptable": False,  # < 3000ms
        "errors": [],
    }

    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=HEADERS,
        follow_redirects=True, verify=False
    ) as client:
        for scheme in ("https", "http"):
            try:
                start = time.monotonic()
                resp = await client.get(f"{scheme}://{domain}")
                elapsed_ms = round((time.monotonic() - start) * 1000)

                result["response_time_ms"] = elapsed_ms
                result["page_size_kb"] = round(len(resp.content) / 1024, 1)
                result["is_fast"] = elapsed_ms < 1000
                result["is_acceptable"] = elapsed_ms < 3000
                break

            except httpx.TimeoutException:
                result["errors"].append(f"{scheme}: request timed out (>15s)")
            except Exception as e:
                result["errors"].append(f"{scheme}: {str(e)[:80]}")

    # ── Score ─────────────────────────────────────────────────────────────────
    score = 0
    ms = result.get("response_time_ms")
    if ms is not None:
        if ms < 500:
            score = 100
        elif ms < 1000:
            score = 80
        elif ms < 2000:
            score = 60
        elif ms < 3000:
            score = 40
        elif ms < 5000:
            score = 20
        else:
            score = 5

    result["score"] = score
    return result
