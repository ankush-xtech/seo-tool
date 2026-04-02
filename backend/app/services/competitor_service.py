"""
Competitor Analysis Service
============================
Discovers competitors for a target domain via SerpAPI Google Search and
optionally Semrush, runs SEO checks, and generates actionable insights.
"""

import asyncio
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import (
    CompetitorAnalysis, CompetitorAnalysisStatus, Competitor,
    CompetitorInsight, InsightSeverity, BusinessListing,
)
from app.services import semrush_client
from app.services.seo_engine import run_all_checks

logger = logging.getLogger(__name__)

# ── Global progress tracker (same pattern as maps.py) ───────────────────────

_progress = {
    "running": False,
    "total": 0,
    "done": 0,
    "failed": 0,
    "phase": "",
    "started_at": None,
    "analysis_id": None,
}
_progress_lock = threading.Lock()

# Directories / aggregators to exclude from competitor results
EXCLUDED_DOMAINS = {
    "yelp.com", "yelp.com.au", "yellowpages.com.au", "yellowpages.com",
    "truelocal.com.au", "hotfrog.com.au", "localsearch.com.au",
    "oneflare.com.au", "hipages.com.au", "productreview.com.au",
    "google.com", "google.com.au", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "linkedin.com", "youtube.com",
    "tiktok.com", "pinterest.com", "reddit.com",
    "wikipedia.org", "en.wikipedia.org",
    "whirlpool.net.au", "serviceseeking.com.au",
    "airtasker.com", "bark.com",
}


def extract_domain(url: str) -> Optional[str]:
    """Extract clean domain from URL."""
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or None
    except Exception:
        return None


def _is_excluded(domain: str) -> bool:
    """Check if domain should be excluded (directories, social, etc.)."""
    if not domain:
        return True
    for exc in EXCLUDED_DOMAINS:
        if domain == exc or domain.endswith("." + exc):
            return True
    if domain.endswith(".gov.au") or domain.endswith(".edu.au"):
        return True
    return False


# ── SerpAPI Google Search for competitor discovery ──────────────────────────

def _discover_via_serpapi(category: str, city: str, state: str,
                          target_domain: str, limit: int = 20) -> list[dict]:
    """Use SerpAPI organic Google Search to find competitor domains."""
    api_key = settings.SERPAPI_KEY
    if not api_key:
        logger.warning("SerpAPI key not configured, skipping Google Search discovery")
        return []

    query = f"{category} {city}".strip()
    if not query:
        return []

    location = f"{city}, {state}, Australia" if state else f"{city}, Australia"

    params = {
        "engine": "google",
        "q": query,
        "location": location,
        "google_domain": "google.com.au",
        "gl": "au",
        "hl": "en",
        "num": str(min(limit, 20)),
        "api_key": api_key,
    }

    try:
        resp = httpx.get("https://serpapi.com/search", params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"SerpAPI Google Search failed: {e}")
        return []

    competitors = []
    seen = set()
    target_clean = extract_domain(target_domain)

    for result in data.get("organic_results", []):
        link = result.get("link", "")
        domain = extract_domain(link)
        if not domain or domain in seen or domain == target_clean or _is_excluded(domain):
            continue
        seen.add(domain)
        competitors.append({
            "domain": domain,
            "business_name": result.get("title", ""),
            "discovery_source": "google_search",
            "search_rank": result.get("position"),
        })

    logger.info(f"SerpAPI Google Search found {len(competitors)} competitors for '{query}'")
    return competitors


# ── Semrush competitor discovery ────────────────────────────────────────────

def _discover_via_semrush(target_domain: str, limit: int = 10) -> list[dict]:
    """Use Semrush organic competitors API."""
    if not semrush_client.is_available():
        return []

    raw = semrush_client.get_organic_competitors(target_domain, limit=limit)
    target_clean = extract_domain(target_domain)

    competitors = []
    for row in raw:
        domain = row.get("domain", "")
        if not domain or domain == target_clean or _is_excluded(domain):
            continue
        competitors.append({
            "domain": domain,
            "business_name": None,
            "discovery_source": "semrush_organic",
            "search_rank": None,
        })

    logger.info(f"Semrush found {len(competitors)} organic competitors for {target_domain}")
    return competitors


# ── Enrich a single competitor ──────────────────────────────────────────────

def _enrich_competitor(domain: str, include_seo: bool, include_semrush: bool) -> dict:
    """Run SEO checks + fetch Semrush data for a single domain."""
    result = {"domain": domain}

    # SEO checks (async, run in new event loop since we're in a thread)
    if include_seo:
        try:
            loop = asyncio.new_event_loop()
            seo_data = loop.run_until_complete(run_all_checks(domain))
            loop.close()
            result["seo_overall_score"] = seo_data.get("overall_score")
            for check in ["dns", "https", "meta", "robots", "sitemap", "ssl",
                          "speed", "mobile", "social_meta", "headings"]:
                result[f"seo_{check}_score"] = seo_data.get(check, {}).get("score")
        except Exception as e:
            logger.warning(f"SEO checks failed for {domain}: {e}")

    # Semrush metrics
    if include_semrush and semrush_client.is_available():
        try:
            overview = semrush_client.get_domain_overview(domain)
            result["semrush_rank"] = overview.get("semrush_rank")
            result["organic_traffic"] = overview.get("organic_traffic")
            result["organic_keywords"] = overview.get("organic_keywords")
            result["domain_authority"] = overview.get("authority_score")

            backlinks = semrush_client.get_backlinks_overview(domain)
            result["backlinks_total"] = backlinks.get("backlinks_total")
            result["referring_domains"] = backlinks.get("referring_domains")

            result["semrush_data"] = {"overview": overview, "backlinks": backlinks}
        except Exception as e:
            logger.warning(f"Semrush fetch failed for {domain}: {e}")

    return result


# ── Match competitor to existing business listing ───────────────────────────

def _match_listing(db, domain: str) -> Optional[BusinessListing]:
    """Try to find a BusinessListing whose website matches this domain."""
    listings = db.query(BusinessListing).filter(
        BusinessListing.website.isnot(None),
        BusinessListing.website != "",
    ).limit(500).all()

    for listing in listings:
        listing_domain = extract_domain(listing.website)
        if listing_domain == domain:
            return listing
    return None


# ── Insight generation ──────────────────────────────────────────────────────

def _generate_insights(target: dict, competitors: list[dict]) -> list[dict]:
    """Compare target vs competitors and produce actionable insights."""
    insights = []
    if not competitors:
        return insights

    # Helper to get median of a metric across competitors
    def median_of(key):
        vals = [c.get(key) for c in competitors if c.get(key) is not None]
        if not vals:
            return None
        vals.sort()
        mid = len(vals) // 2
        return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2

    def avg_of(key):
        vals = [c.get(key) for c in competitors if c.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    # 1. SEO check gaps
    seo_checks = ["dns", "https", "meta", "robots", "sitemap", "ssl",
                   "speed", "mobile", "social_meta", "headings"]
    for check in seo_checks:
        key = f"seo_{check}_score"
        target_score = target.get(key)
        comp_avg = avg_of(key)
        if target_score is not None and comp_avg is not None:
            if target_score < 40 and comp_avg > 60:
                insights.append({
                    "insight_type": "missing_check",
                    "severity": "high",
                    "title": f"Poor {check.replace('_', ' ').title()} Score",
                    "description": (
                        f"Target scores {target_score:.0f}/100 on {check.replace('_', ' ')} "
                        f"while competitors average {comp_avg:.0f}/100. "
                        f"This is a critical area for improvement."
                    ),
                    "meta": {"check": check, "target_score": target_score, "competitor_avg": comp_avg},
                })
            elif target_score < comp_avg - 20:
                insights.append({
                    "insight_type": "missing_check",
                    "severity": "medium",
                    "title": f"Below Average {check.replace('_', ' ').title()} Score",
                    "description": (
                        f"Target scores {target_score:.0f}/100 vs competitor average "
                        f"of {comp_avg:.0f}/100 on {check.replace('_', ' ')}."
                    ),
                    "meta": {"check": check, "target_score": target_score, "competitor_avg": comp_avg},
                })

    # 2. Overall SEO gap
    target_overall = target.get("seo_overall_score")
    comp_overall_avg = avg_of("seo_overall_score")
    if target_overall is not None and comp_overall_avg is not None:
        if target_overall < comp_overall_avg - 15:
            insights.append({
                "insight_type": "missing_check",
                "severity": "high",
                "title": "Overall SEO Score Below Competitors",
                "description": (
                    f"Overall SEO score is {target_overall:.0f} vs competitor average "
                    f"of {comp_overall_avg:.0f}. Significant improvement opportunity."
                ),
                "meta": {"target_score": target_overall, "competitor_avg": comp_overall_avg},
            })

    # 3. Keyword gap
    target_kw = target.get("organic_keywords")
    median_kw = median_of("organic_keywords")
    if target_kw is not None and median_kw is not None and median_kw > 0:
        if target_kw < median_kw * 0.5:
            insights.append({
                "insight_type": "keyword_gap",
                "severity": "high",
                "title": "Significantly Fewer Organic Keywords",
                "description": (
                    f"Target ranks for {target_kw:,} keywords while the median "
                    f"competitor ranks for {median_kw:,.0f}. Content strategy needed."
                ),
                "meta": {"target": target_kw, "competitor_median": median_kw},
            })
        elif target_kw < median_kw:
            insights.append({
                "insight_type": "keyword_gap",
                "severity": "medium",
                "title": "Fewer Organic Keywords Than Competitors",
                "description": (
                    f"Target ranks for {target_kw:,} keywords vs median {median_kw:,.0f}."
                ),
                "meta": {"target": target_kw, "competitor_median": median_kw},
            })

    # 4. Backlink gap
    target_bl = target.get("referring_domains")
    median_bl = median_of("referring_domains")
    if target_bl is not None and median_bl is not None and median_bl > 0:
        if target_bl < median_bl * 0.3:
            insights.append({
                "insight_type": "backlink_gap",
                "severity": "high",
                "title": "Very Few Referring Domains",
                "description": (
                    f"Target has {target_bl:,} referring domains vs competitor median "
                    f"of {median_bl:,.0f}. Link building is a priority."
                ),
                "meta": {"target": target_bl, "competitor_median": median_bl},
            })

    # 5. Traffic gap
    target_traffic = target.get("organic_traffic")
    median_traffic = median_of("organic_traffic")
    if target_traffic is not None and median_traffic is not None and median_traffic > 0:
        if target_traffic < median_traffic * 0.3:
            insights.append({
                "insight_type": "traffic_gap",
                "severity": "high",
                "title": "Significantly Lower Organic Traffic",
                "description": (
                    f"Target gets ~{target_traffic:,} organic visits/month vs "
                    f"competitor median of ~{median_traffic:,.0f}."
                ),
                "meta": {"target": target_traffic, "competitor_median": median_traffic},
            })

    # 6. Maps rating gap
    target_rating = target.get("maps_rating")
    avg_rating = avg_of("maps_rating")
    if target_rating is not None and avg_rating is not None:
        if target_rating < avg_rating - 0.5:
            insights.append({
                "insight_type": "rating_gap",
                "severity": "medium",
                "title": "Lower Google Maps Rating",
                "description": (
                    f"Target rated {target_rating:.1f} stars vs competitor average "
                    f"of {avg_rating:.1f}. Review management could help."
                ),
                "meta": {"target": target_rating, "competitor_avg": avg_rating},
            })

    # Sort by severity: high first
    severity_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return insights


# ── Main background thread ──────────────────────────────────────────────────

def run_competitor_analysis(analysis_id: int, include_seo: bool = True,
                            include_semrush: bool = True, max_competitors: int = 10):
    """Run competitor analysis in a background thread."""
    db = SessionLocal()
    try:
        analysis = db.query(CompetitorAnalysis).filter(
            CompetitorAnalysis.id == analysis_id
        ).first()
        if not analysis:
            logger.error(f"CompetitorAnalysis {analysis_id} not found")
            return

        analysis.status = CompetitorAnalysisStatus.running
        db.commit()

        with _progress_lock:
            _progress["running"] = True
            _progress["total"] = 0
            _progress["done"] = 0
            _progress["failed"] = 0
            _progress["phase"] = "discovering"
            _progress["started_at"] = datetime.now(timezone.utc).isoformat()
            _progress["analysis_id"] = analysis_id

        # ── Step 1: Discover competitors ────────────────────────────────────
        all_competitors = []

        # SerpAPI Google Search
        if analysis.target_category and analysis.target_city:
            serpapi_results = _discover_via_serpapi(
                analysis.target_category,
                analysis.target_city,
                analysis.target_state or "",
                analysis.target_domain,
                limit=max_competitors + 5,
            )
            all_competitors.extend(serpapi_results)

        # Semrush organic competitors
        if include_semrush:
            semrush_results = _discover_via_semrush(analysis.target_domain, limit=max_competitors)
            # Merge without duplicates
            seen = {c["domain"] for c in all_competitors}
            for comp in semrush_results:
                if comp["domain"] not in seen:
                    all_competitors.append(comp)
                    seen.add(comp["domain"])

            if semrush_results:
                analysis.discovery_method = "both" if all_competitors else "semrush"
            else:
                analysis.discovery_method = "serpapi"
        else:
            analysis.discovery_method = "serpapi"

        # Cap at max
        all_competitors = all_competitors[:max_competitors]

        with _progress_lock:
            # +1 for the target domain itself
            _progress["total"] = len(all_competitors) + 1
            _progress["phase"] = "enriching"

        logger.info(f"Discovered {len(all_competitors)} competitors, starting enrichment...")

        # ── Step 2: Enrich target domain ────────────────────────────────────
        target_data = _enrich_competitor(analysis.target_domain, include_seo, include_semrush)
        target_data["is_target"] = True
        target_data["discovery_source"] = "target"

        # Match target to existing listing
        if analysis.business_listing_id:
            listing = db.query(BusinessListing).filter(
                BusinessListing.id == analysis.business_listing_id
            ).first()
            if listing:
                target_data["business_name"] = listing.business_name
                target_data["maps_rating"] = listing.rating
                target_data["maps_reviews"] = listing.reviews_count
                target_data["listing_id"] = listing.id

        target_comp = Competitor(
            analysis_id=analysis_id,
            **{k: v for k, v in target_data.items() if k != "semrush_data" and hasattr(Competitor, k)},
            semrush_data=target_data.get("semrush_data"),
        )
        db.add(target_comp)
        db.commit()

        with _progress_lock:
            _progress["done"] = 1

        # ── Step 3: Enrich competitors in parallel ──────────────────────────
        enriched_competitors = []

        def _process_one(comp_info):
            data = _enrich_competitor(comp_info["domain"], include_seo, include_semrush)
            data["business_name"] = comp_info.get("business_name")
            data["discovery_source"] = comp_info.get("discovery_source")
            data["search_rank"] = comp_info.get("search_rank")
            return data

        with ThreadPoolExecutor(max_workers=settings.COMPETITOR_WORKER_THREADS) as executor:
            future_map = {
                executor.submit(_process_one, c): c for c in all_competitors
            }
            for future in as_completed(future_map):
                try:
                    data = future.result()

                    # Match to existing listing
                    matched = _match_listing(db, data["domain"])
                    if matched:
                        data["listing_id"] = matched.id
                        data["maps_rating"] = matched.rating
                        data["maps_reviews"] = matched.reviews_count
                        if not data.get("business_name"):
                            data["business_name"] = matched.business_name

                    comp = Competitor(
                        analysis_id=analysis_id,
                        **{k: v for k, v in data.items() if k != "semrush_data" and hasattr(Competitor, k)},
                        semrush_data=data.get("semrush_data"),
                    )
                    db.add(comp)
                    db.commit()
                    enriched_competitors.append(data)

                    with _progress_lock:
                        _progress["done"] += 1

                except Exception as e:
                    logger.error(f"Failed to enrich competitor: {e}")
                    db.rollback()
                    with _progress_lock:
                        _progress["failed"] += 1

        # ── Step 4: Generate insights ───────────────────────────────────────
        with _progress_lock:
            _progress["phase"] = "analyzing"

        insights = _generate_insights(target_data, enriched_competitors)

        for insight_data in insights:
            severity = InsightSeverity(insight_data["severity"])
            insight = CompetitorInsight(
                analysis_id=analysis_id,
                insight_type=insight_data["insight_type"],
                severity=severity,
                title=insight_data["title"],
                description=insight_data["description"],
                meta=insight_data.get("meta"),
            )
            db.add(insight)

        # ── Finalize ────────────────────────────────────────────────────────
        analysis.status = CompetitorAnalysisStatus.done
        analysis.competitors_found = len(enriched_competitors)
        db.commit()

        logger.info(
            f"Competitor analysis complete: {len(enriched_competitors)} competitors, "
            f"{len(insights)} insights for {analysis.target_domain}"
        )

    except Exception as e:
        logger.error(f"Competitor analysis thread error: {e}", exc_info=True)
        try:
            analysis = db.query(CompetitorAnalysis).filter(
                CompetitorAnalysis.id == analysis_id
            ).first()
            if analysis:
                analysis.status = CompetitorAnalysisStatus.failed
                analysis.error_message = str(e)[:500]
                db.commit()
        except Exception:
            pass
    finally:
        with _progress_lock:
            _progress["running"] = False
            _progress["phase"] = "done"
        db.close()


def get_progress() -> dict:
    """Get current analysis progress."""
    with _progress_lock:
        p = dict(_progress)
    if p["total"] > 0:
        p["percent"] = round((p["done"] + p["failed"]) / p["total"] * 100, 1)
    else:
        p["percent"] = 0
    return p
