"""
DNS Check
=========
Verifies that a domain has valid DNS records (A, CNAME, MX, NS).
Score: 0-100
"""

import asyncio
import logging
from typing import Any
import dns.resolver
import dns.exception

logger = logging.getLogger(__name__)


async def check_dns(domain: str) -> dict[str, Any]:
    """
    Check DNS records for a domain.
    Returns score (0-100) and detailed data.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _check_dns_sync, domain)


def _check_dns_sync(domain: str) -> dict[str, Any]:
    result = {
        "score": 0,
        "has_a_record": False,
        "has_mx_record": False,
        "has_ns_record": False,
        "a_records": [],
        "mx_records": [],
        "ns_records": [],
        "errors": [],
    }

    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 5

    # ── A Record (most important — domain resolves to IP) ─────────────────────
    try:
        answers = resolver.resolve(domain, "A")
        result["has_a_record"] = True
        result["a_records"] = [str(r) for r in answers]
    except dns.exception.DNSException as e:
        result["errors"].append(f"A record: {str(e)[:100]}")

    # ── MX Record (mail) ──────────────────────────────────────────────────────
    try:
        answers = resolver.resolve(domain, "MX")
        result["has_mx_record"] = True
        result["mx_records"] = [str(r.exchange) for r in answers]
    except dns.exception.DNSException:
        pass  # MX is optional

    # ── NS Record (nameservers) ───────────────────────────────────────────────
    try:
        answers = resolver.resolve(domain, "NS")
        result["has_ns_record"] = True
        result["ns_records"] = [str(r) for r in answers]
    except dns.exception.DNSException as e:
        result["errors"].append(f"NS record: {str(e)[:100]}")

    # ── Score calculation ─────────────────────────────────────────────────────
    score = 0
    if result["has_a_record"]:
        score += 60   # A record is most critical
    if result["has_ns_record"]:
        score += 25
    if result["has_mx_record"]:
        score += 15

    result["score"] = min(score, 100)
    return result
