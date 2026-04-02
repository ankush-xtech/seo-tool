"""
Semrush REST API Client
=======================
Simple HTTP client for Semrush API (https://api.semrush.com/).
Parses semicolon-delimited CSV responses into Python dicts.

Gracefully degrades when API key is not configured — returns empty results.
"""

import io
import csv
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.semrush.com/"


def _parse_csv_response(text: str) -> list[dict]:
    """Parse Semrush semicolon-delimited CSV response into list of dicts."""
    if not text or text.startswith("ERROR"):
        if text:
            logger.warning(f"Semrush API error: {text.strip()}")
        return []
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


def _request(report_type: str, params: dict, timeout: float = 15.0) -> list[dict]:
    """Make HTTP GET to Semrush API, return parsed rows."""
    api_key = settings.SEMRUSH_API_KEY
    if not api_key:
        logger.debug("Semrush API key not configured, skipping request")
        return []

    query = {
        "type": report_type,
        "key": api_key,
        **params,
    }

    try:
        resp = httpx.get(BASE_URL, params=query, timeout=timeout)
        resp.raise_for_status()
        return _parse_csv_response(resp.text)
    except httpx.TimeoutException:
        logger.warning(f"Semrush request timed out: {report_type}")
        return []
    except httpx.HTTPStatusError as e:
        logger.warning(f"Semrush HTTP error {e.response.status_code}: {report_type}")
        return []
    except Exception as e:
        logger.error(f"Semrush request failed: {e}")
        return []


def get_domain_overview(domain: str, database: Optional[str] = None) -> dict:
    """
    Get domain overview: traffic, keywords, authority score.
    Returns dict with keys like Ot (organic traffic), Ok (organic keywords), As (authority score).
    """
    db = database or settings.SEMRUSH_DATABASE
    rows = _request("domain_rank", {
        "domain": domain,
        "database": db,
        "export_columns": "Dn,Rk,Or,Ot,Oc,Ad,At,Ac,As",
    })
    if not rows:
        return {}

    row = rows[0]
    return {
        "domain": row.get("Dn", domain),
        "semrush_rank": _int(row.get("Rk")),
        "organic_keywords": _int(row.get("Or")),
        "organic_traffic": _int(row.get("Ot")),
        "organic_cost": _float(row.get("Oc")),
        "ads_keywords": _int(row.get("Ad")),
        "ads_traffic": _int(row.get("At")),
        "ads_cost": _float(row.get("Ac")),
        "authority_score": _float(row.get("As")),
    }


def get_organic_competitors(domain: str, database: Optional[str] = None, limit: int = 10) -> list[dict]:
    """
    Get domains competing for the same organic keywords.
    Returns list of competitor dicts.
    """
    db = database or settings.SEMRUSH_DATABASE
    rows = _request("domain_organic_organic", {
        "domain": domain,
        "database": db,
        "display_limit": str(limit),
        "export_columns": "Dn,Cr,Np,Or,Ot,Oc,Ad,As",
    })

    competitors = []
    for row in rows:
        competitors.append({
            "domain": row.get("Dn", ""),
            "common_keywords": _int(row.get("Np")),
            "competition_level": _float(row.get("Cr")),
            "organic_keywords": _int(row.get("Or")),
            "organic_traffic": _int(row.get("Ot")),
            "organic_cost": _float(row.get("Oc")),
            "ads_keywords": _int(row.get("Ad")),
            "authority_score": _float(row.get("As")),
        })
    return competitors


def get_backlinks_overview(domain: str) -> dict:
    """
    Get backlink profile summary.
    Returns dict with total backlinks, referring domains, etc.
    """
    rows = _request("backlinks_overview", {
        "target": domain,
        "target_type": "root_domain",
        "export_columns": "total,domains_num,urls_num,ips_num,follows_num,nofollows_num,texts_num,images_num",
    })
    if not rows:
        return {}

    row = rows[0]
    return {
        "backlinks_total": _int(row.get("total")),
        "referring_domains": _int(row.get("domains_num")),
        "referring_urls": _int(row.get("urls_num")),
        "referring_ips": _int(row.get("ips_num")),
        "follow_links": _int(row.get("follows_num")),
        "nofollow_links": _int(row.get("nofollows_num")),
    }


def is_available() -> bool:
    """Check if Semrush API key is configured."""
    return bool(settings.SEMRUSH_API_KEY)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _int(val) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _float(val) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None
