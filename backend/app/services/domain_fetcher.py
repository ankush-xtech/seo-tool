"""
Domain Fetcher Service
======================
Fetches newly registered domains from multiple sources:

  1. WhoisDS.com     — Free daily CSV (primary)
  2. DomainBigData   — API with richer metadata (secondary, needs API key)
  3. ICANN zone file — Raw .com/.net zone files (fallback, large)

Each source returns a list of DomainRecord dicts:
  { name, tld, registrar, registered_at }
"""

import csv
import io
import zipfile
import logging
import asyncio
from datetime import datetime, timezone, date
from typing import AsyncGenerator
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Data Class ───────────────────────────────────────────────────────────────

@dataclass
class DomainRecord:
    name: str                               # e.g. "example.com"
    tld: str                                # e.g. "com"
    registrar: str | None = None
    registered_at: datetime | None = None
    source: str = "unknown"

    def __post_init__(self):
        self.name = self.name.lower().strip()
        self.tld = self.tld.lower().strip().lstrip(".")


# ─── HTTP Client ──────────────────────────────────────────────────────────────

def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0; +https://yourdomain.com/bot)",
        },
        follow_redirects=True,
    )


# ─── Source 1: WhoisDS.com ────────────────────────────────────────────────────

async def fetch_whoisds(fetch_date: date | None = None) -> list[DomainRecord]:
    """
    Fetches the daily newly-registered domains CSV from WhoisDS.com.
    URL pattern: https://www.whoisds.com/newly-registered-domains
    They provide a downloadable ZIP/CSV per day.

    Free tier provides the last 1-day list without registration.
    """
    target_date = fetch_date or date.today()
    date_str = target_date.strftime("%Y-%m-%d")

    # WhoisDS encodes date as base64 in the URL for their download link
    import base64
    encoded = base64.b64encode(f"{date_str}.zip".encode()).decode()
    url = f"https://www.whoisds.com//whois-database/newly-registered-domains/{encoded}/nrd"

    logger.info(f"[WhoisDS] Fetching domains for {date_str} — URL: {url}")

    try:
        import requests as req_lib
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = req_lib.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        content = resp.content
        logger.info(f"[WhoisDS] Downloaded {len(content):,} bytes")

        records: list[DomainRecord] = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            txt_files = [f for f in zf.namelist() if not f.endswith("/")]
            logger.info(f"[WhoisDS] ZIP contains: {txt_files}")
            for fname in txt_files:
                with zf.open(fname) as f:
                    for raw_line in f:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line or line.startswith("#"):
                            continue
                        record = _parse_domain_line(line, source="whoisds")
                        if record:
                            records.append(record)

        logger.info(f"[WhoisDS] Parsed {len(records):,} domains")
        return records

    except Exception as e:
        logger.error(f"[WhoisDS] Error: {type(e).__name__}: {e}")
        return []


# ─── Source 2: DomainBigData API ─────────────────────────────────────────────

async def fetch_domainbigdata(
    fetch_date: date | None = None,
    api_key: str | None = None,
) -> list[DomainRecord]:
    """
    Fetches from DomainBigData API — provides richer metadata including registrar.
    Requires an API key (set DOMAINBIGDATA_API_KEY in .env).
    Docs: https://domainbigdata.com/api
    """
    key = api_key or getattr(settings, "DOMAINBIGDATA_API_KEY", None)
    if not key:
        logger.warning("[DomainBigData] No API key configured — skipping")
        return []

    target_date = fetch_date or date.today()
    date_str = target_date.strftime("%Y-%m-%d")

    url = "https://domainbigdata.com/api/v1/newly-registered"
    params = {"date": date_str, "apikey": key, "format": "csv"}

    logger.info(f"[DomainBigData] Fetching domains for {date_str}")

    try:
        async with _make_client() as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

            records: list[DomainRecord] = []
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                domain = row.get("domain", "").strip().lower()
                if not domain:
                    continue
                tld = domain.split(".")[-1] if "." in domain else ""
                registrar = row.get("registrar", None)
                reg_date_str = row.get("registration_date", None)
                registered_at = _parse_date(reg_date_str)

                records.append(DomainRecord(
                    name=domain,
                    tld=tld,
                    registrar=registrar,
                    registered_at=registered_at,
                    source="domainbigdata",
                ))

            logger.info(f"[DomainBigData] Fetched {len(records):,} domains")
            return records

    except Exception as e:
        logger.error(f"[DomainBigData] Error: {e}")
        return []


# ─── Source 3: ICANN .com Zone File (Fallback) ────────────────────────────────

async def fetch_icann_zone(tld: str = "com") -> list[DomainRecord]:
    """
    Downloads the raw ICANN zone file for .com or .net.
    These are VERY large files (millions of records).
    Requires CZDS (Centralized Zone Data Service) account:
    https://czds.icann.org/

    This is a last-resort fallback. Only use if WhoisDS + DomainBigData both fail.
    """
    czds_token = getattr(settings, "ICANN_CZDS_TOKEN", None)
    if not czds_token:
        logger.warning("[ICANN] No CZDS token configured — skipping zone file fetch")
        return []

    url = f"https://czds-api.icann.org/czds/downloads/{tld}.zone"
    headers = {"Authorization": f"Bearer {czds_token}"}

    logger.info(f"[ICANN] Downloading .{tld} zone file (this may take a while)...")

    records: list[DomainRecord] = []
    seen: set[str] = set()

    try:
        async with _make_client() as client:
            async with client.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                async for line_bytes in resp.aiter_lines():
                    line = line_bytes.strip()
                    # Zone file format: <domain>.<tld>. <TTL> IN NS <nameserver>
                    if "\tNS\t" not in line and " NS " not in line:
                        continue
                    parts = line.split()
                    if not parts:
                        continue
                    raw = parts[0].rstrip(".").lower()
                    if "." not in raw or raw in seen:
                        continue
                    seen.add(raw)
                    records.append(DomainRecord(
                        name=f"{raw}.{tld}",
                        tld=tld,
                        source="icann_zone",
                    ))

        logger.info(f"[ICANN] Zone file yielded {len(records):,} {tld} domains")
        return records

    except Exception as e:
        logger.error(f"[ICANN] Error fetching zone file: {e}")
        return []


# ─── Aggregator: fetch from all available sources ─────────────────────────────

async def fetch_all_sources(fetch_date: date | None = None) -> list[DomainRecord]:
    """
    Runs all available sources concurrently and merges + deduplicates results.
    Returns a deduplicated list of DomainRecord objects.
    """
    target_date = fetch_date or date.today()
    logger.info(f"[Fetcher] Starting domain fetch for {target_date}")

    # Run primary + secondary sources concurrently
    results = await asyncio.gather(
        fetch_whoisds(target_date),
        fetch_domainbigdata(target_date),
        return_exceptions=True,
    )

    all_records: list[DomainRecord] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"[Fetcher] Source failed: {result}")
        elif isinstance(result, list):
            all_records.extend(result)

    # Deduplicate by domain name (prefer records with more metadata)
    deduped = _deduplicate(all_records)

    # Filter out junk
    filtered = _filter_domains(deduped)

    logger.info(
        f"[Fetcher] Done — raw: {len(all_records):,} | "
        f"deduped: {len(deduped):,} | filtered: {len(filtered):,}"
    )
    return filtered


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_domain_line(line: str, source: str = "unknown") -> DomainRecord | None:
    """Parse a bare domain line like 'example.com' or CSV with columns."""
    line = line.strip().lower()
    if not line or "." not in line:
        return None

    # Strip protocol if accidentally included
    for prefix in ("http://", "https://", "www."):
        if line.startswith(prefix):
            line = line[len(prefix):]

    # Take first token if space/tab separated
    domain = line.split()[0].rstrip(".,;")

    if not _is_valid_domain(domain):
        return None

    tld = domain.split(".")[-1]
    return DomainRecord(name=domain, tld=tld, source=source)


def _is_valid_domain(domain: str) -> bool:
    """Basic domain validity check."""
    import re
    if len(domain) > 253 or len(domain) < 3:
        return False
    if domain.count(".") < 1:
        return False
    pattern = r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)*$"
    return bool(re.match(pattern, domain))


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# TLDs commonly used for spam/parking — skip these
SPAM_TLDS = {
    "tk", "ml", "ga", "cf", "gq",   # Free TLDs heavily abused
    "xyz",                             # Optional — high spam ratio
}

# Known parking/registrar placeholder patterns
SKIP_PATTERNS = [
    "parking", "sedoparking", "placeholder", "coming-soon",
]


def _filter_domains(records: list[DomainRecord]) -> list[DomainRecord]:
    """Remove spam TLDs, parking domains, and obviously junk entries."""
    filtered = []
    for r in records:
        if r.tld in SPAM_TLDS:
            continue
        if any(p in r.name for p in SKIP_PATTERNS):
            continue
        filtered.append(r)
    return filtered


def _deduplicate(records: list[DomainRecord]) -> list[DomainRecord]:
    """
    Deduplicate by domain name.
    When duplicates exist, prefer the record with more metadata (registrar + date).
    """
    seen: dict[str, DomainRecord] = {}
    for r in records:
        if r.name not in seen:
            seen[r.name] = r
        else:
            existing = seen[r.name]
            # Prefer record with registrar info
            if r.registrar and not existing.registrar:
                seen[r.name] = r
            # Prefer record with registration date
            elif r.registered_at and not existing.registered_at:
                seen[r.name] = r
    return list(seen.values())
