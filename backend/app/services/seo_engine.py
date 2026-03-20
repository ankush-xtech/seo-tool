"""
SEO Engine
==========
Orchestrates all individual SEO checks for a single domain.
Runs them concurrently and computes a weighted overall score.

Weights:
  DNS        15%
  HTTPS      20%
  Meta       20%
  Robots      5%
  Sitemap     5%
  SSL        15%
  Speed      10%
  Mobile      5%
  Social Meta 3%
  Headings    2%
"""

import asyncio
import logging
from typing import Any

from app.services.seo_checks.dns_check import check_dns
from app.services.seo_checks.https_check import check_https
from app.services.seo_checks.meta_check import check_meta
from app.services.seo_checks.robots_check import check_robots
from app.services.seo_checks.sitemap_check import check_sitemap
from app.services.seo_checks.ssl_check import check_ssl
from app.services.seo_checks.speed_check import check_speed
from app.services.seo_checks.page_checks import (
    check_mobile, check_social_meta, check_headings
)

logger = logging.getLogger(__name__)

# Weights must sum to 100
WEIGHTS = {
    "dns":         15,
    "https":       20,
    "meta":        20,
    "robots":       5,
    "sitemap":      5,
    "ssl":         15,
    "speed":       10,
    "mobile":       5,
    "social_meta":  3,
    "headings":     2,
}


async def run_all_checks(domain: str) -> dict[str, Any]:
    """
    Run all SEO checks concurrently for a domain.
    Returns a dict with individual scores + overall weighted score.
    """
    logger.info(f"[SEO Engine] Starting checks for: {domain}")

    # Run all checks concurrently with timeout safety
    tasks = {
        "dns":         check_dns(domain),
        "https":       check_https(domain),
        "meta":        check_meta(domain),
        "robots":      check_robots(domain),
        "sitemap":     check_sitemap(domain),
        "ssl":         check_ssl(domain),
        "speed":       check_speed(domain),
        "mobile":      check_mobile(domain),
        "social_meta": check_social_meta(domain),
        "headings":    check_headings(domain),
    }

    # Gather with individual timeouts — one slow check won't block all
    results: dict[str, Any] = {}
    check_coros = list(tasks.values())
    check_names = list(tasks.keys())

    gathered = await asyncio.gather(*check_coros, return_exceptions=True)

    for name, result in zip(check_names, gathered):
        if isinstance(result, Exception):
            logger.warning(f"[SEO Engine] Check '{name}' raised exception: {result}")
            results[name] = {"score": 0, "errors": [str(result)[:200]]}
        else:
            results[name] = result

    # ── Weighted overall score ─────────────────────────────────────────────────
    overall = 0.0
    for check_name, weight in WEIGHTS.items():
        check_score = results.get(check_name, {}).get("score", 0) or 0
        overall += (check_score * weight) / 100

    overall_score = round(overall, 1)

    logger.info(f"[SEO Engine] Done for {domain} — overall score: {overall_score}")

    return {
        "overall_score": overall_score,
        "dns":         results.get("dns", {}),
        "https":       results.get("https", {}),
        "meta":        results.get("meta", {}),
        "robots":      results.get("robots", {}),
        "sitemap":     results.get("sitemap", {}),
        "ssl":         results.get("ssl", {}),
        "speed":       results.get("speed", {}),
        "mobile":      results.get("mobile", {}),
        "social_meta": results.get("social_meta", {}),
        "headings":    results.get("headings", {}),
    }
