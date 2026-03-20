"""
SSL Certificate Check
=====================
Checks SSL certificate validity, expiry, and issuer.
Score: 0-100
"""

import ssl
import socket
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def check_ssl(domain: str) -> dict[str, Any]:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _check_ssl_sync, domain)


def _check_ssl_sync(domain: str) -> dict[str, Any]:
    result = {
        "score": 0,
        "has_ssl": False,
        "is_valid": False,
        "is_expired": False,
        "days_until_expiry": None,
        "expiry_date": None,
        "issuer": None,
        "subject": None,
        "errors": [],
    }

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

                result["has_ssl"] = True
                result["is_valid"] = True

                # Expiry
                not_after_str = cert.get("notAfter", "")
                if not_after_str:
                    not_after = datetime.strptime(
                        not_after_str, "%b %d %H:%M:%S %Y %Z"
                    ).replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    days_left = (not_after - now).days
                    result["expiry_date"] = not_after.strftime("%Y-%m-%d")
                    result["days_until_expiry"] = days_left
                    result["is_expired"] = days_left < 0

                # Issuer
                issuer = dict(x[0] for x in cert.get("issuer", []))
                result["issuer"] = issuer.get("organizationName", "Unknown")[:100]

                # Subject
                subject = dict(x[0] for x in cert.get("subject", []))
                result["subject"] = subject.get("commonName", domain)[:100]

    except ssl.SSLCertVerificationError as e:
        result["has_ssl"] = True
        result["is_valid"] = False
        result["errors"].append(f"SSL verification failed: {str(e)[:100]}")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        result["errors"].append(f"Could not connect to port 443: {str(e)[:100]}")
    except Exception as e:
        result["errors"].append(f"SSL check error: {str(e)[:100]}")

    # ── Score ─────────────────────────────────────────────────────────────────
    score = 0
    if result["has_ssl"]:
        score += 40
    if result["is_valid"] and not result["is_expired"]:
        score += 40
    days = result.get("days_until_expiry")
    if days is not None:
        if days > 30:
            score += 20
        elif days > 7:
            score += 10
        # < 7 days = no bonus, expiring soon

    result["score"] = min(score, 100)
    return result
