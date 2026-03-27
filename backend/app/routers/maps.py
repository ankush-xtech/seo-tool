"""
Google Maps Business Listing Extraction
Searches Google Maps via SerpAPI, scrapes emails from business websites,
stores results with real-time progress tracking.
"""
import io
import csv
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.middleware.deps import require_admin, get_current_user
from app.models.models import (
    MapSearchQuery, MapSearchStatus, BusinessListing,
    AuditLog, AuditAction, User,
)
from app.schemas.maps import (
    MapSearchCreate, MapSearchPublic, MapSearchList,
    BusinessListingPublic, BusinessListingList,
    AUSTRALIAN_CITIES, BUSINESS_CATEGORIES,
)
from app.services.maps.provider_factory import get_maps_provider
from app.services.maps.email_scraper import scrape_contact_info
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/maps", tags=["Google Maps"])

# ─── Global progress tracker (same pattern as fetch.py) ──────────────────────

_maps_progress = {
    "running": False,
    "total": 0,
    "done": 0,
    "failed": 0,
    "started_at": None,
    "query_id": None,
}
_maps_progress_lock = threading.Lock()

_maps_recently_found: list[dict] = []
_maps_recently_lock = threading.Lock()
MAX_RECENT = 50


def _add_recently_found(listing_dict: dict):
    with _maps_recently_lock:
        _maps_recently_found.append(listing_dict)
        if len(_maps_recently_found) > MAX_RECENT:
            del _maps_recently_found[:-MAX_RECENT]


# ─── Background search thread ────────────────────────────────────────────────

def _maps_search_thread(query_id: int, max_results: int = 60):
    """Run Google Maps search + email scraping in background."""
    db = SessionLocal()
    try:
        query = db.query(MapSearchQuery).filter(MapSearchQuery.id == query_id).first()
        if not query:
            logger.error(f"MapSearchQuery {query_id} not found")
            return

        query.status = MapSearchStatus.running
        db.commit()

        with _maps_progress_lock:
            _maps_progress["running"] = True
            _maps_progress["total"] = 0
            _maps_progress["done"] = 0
            _maps_progress["failed"] = 0
            _maps_progress["started_at"] = datetime.now(timezone.utc).isoformat()
            _maps_progress["query_id"] = query_id

        # Clear recent buffer for new search
        with _maps_recently_lock:
            _maps_recently_found.clear()

        # Step 1: Fetch listings from provider
        try:
            provider = get_maps_provider()
            search_data = MapSearchCreate(
                query_text=query.query_text,
                category=query.category,
                city=query.city,
                state=query.state,
            )
            results = provider.search(
                search_data.effective_query(),
                search_data.effective_location(),
                max_results=max_results,
            )
        except Exception as e:
            logger.error(f"Maps provider failed: {e}")
            query.status = MapSearchStatus.failed
            query.error_message = str(e)
            db.commit()
            with _maps_progress_lock:
                _maps_progress["running"] = False
            return

        with _maps_progress_lock:
            _maps_progress["total"] = len(results)

        logger.info(f"Maps search returned {len(results)} results, starting email scraping...")

        # Step 2: For each result, scrape email from website in parallel
        def _process_result(result):
            """Process a single business result: scrape email + return dict."""
            email = result.raw_data.get("email") if result.raw_data else None
            phone = result.phone

            # Scrape website for email/phone if website exists
            if result.website and not email:
                try:
                    time.sleep(settings.MAPS_EMAIL_SCRAPE_DELAY)
                    contact = scrape_contact_info(result.website)
                    if contact["email"]:
                        email = contact["email"]
                    if contact["phone"] and not phone:
                        phone = contact["phone"]
                except Exception as e:
                    logger.debug(f"Email scrape failed for {result.website}: {e}")

            return {
                "place_id": result.place_id,
                "business_name": result.business_name,
                "address": result.address,
                "city": result.city or query.city,
                "state": result.state or query.state,
                "postcode": result.postcode,
                "phone": phone,
                "email": email,
                "website": result.website,
                "rating": result.rating,
                "reviews_count": result.reviews_count,
                "category": result.category or query.category,
                "latitude": result.latitude,
                "longitude": result.longitude,
                "raw_data": result.raw_data,
            }

        saved_count = 0
        with ThreadPoolExecutor(max_workers=settings.MAPS_WORKER_THREADS) as executor:
            future_to_result = {
                executor.submit(_process_result, r): r for r in results
            }

            for future in as_completed(future_to_result):
                try:
                    data = future.result()

                    listing = BusinessListing(
                        search_query_id=query_id,
                        **data,
                    )
                    db.add(listing)
                    db.commit()
                    db.refresh(listing)
                    saved_count += 1

                    with _maps_progress_lock:
                        _maps_progress["done"] = saved_count

                    # Add to real-time feed
                    _add_recently_found({
                        "id": listing.id,
                        "business_name": listing.business_name,
                        "address": listing.address,
                        "city": listing.city,
                        "phone": listing.phone,
                        "email": listing.email,
                        "website": listing.website,
                        "rating": listing.rating,
                        "reviews_count": listing.reviews_count,
                        "category": listing.category,
                        "found_at": datetime.now(timezone.utc).isoformat(),
                    })

                except Exception as e:
                    logger.error(f"Failed to save listing: {e}")
                    db.rollback()
                    with _maps_progress_lock:
                        _maps_progress["failed"] += 1

        # Finalize
        query.status = MapSearchStatus.done
        query.results_count = saved_count
        db.commit()
        logger.info(f"Maps search complete: {saved_count} listings saved for query {query_id}")

    except Exception as e:
        logger.error(f"Maps search thread error: {e}", exc_info=True)
        try:
            query = db.query(MapSearchQuery).filter(MapSearchQuery.id == query_id).first()
            if query:
                query.status = MapSearchStatus.failed
                query.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        with _maps_progress_lock:
            _maps_progress["running"] = False
        db.close()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/search")
def start_maps_search(
    data: MapSearchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start a Google Maps business search. Admin only."""
    # Validate input
    effective_query = data.effective_query()
    if not effective_query.strip():
        raise HTTPException(400, "Provide either query_text or category + city")

    # Check if already running
    with _maps_progress_lock:
        if _maps_progress["running"]:
            raise HTTPException(409, "A Maps search is already running. Please wait.")

    # Create search record
    search = MapSearchQuery(
        user_id=current_user.id,
        query_text=effective_query,
        category=data.category,
        city=data.city,
        state=data.state,
        status=MapSearchStatus.pending,
        provider="serpapi" if settings.SERPAPI_KEY else "scraper",
    )
    db.add(search)
    db.commit()
    db.refresh(search)

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.maps_search,
        description=f"Started Maps search: {effective_query}",
    ))
    db.commit()

    # Spawn background thread
    thread = threading.Thread(
        target=_maps_search_thread,
        args=(search.id, data.max_results),
        daemon=True,
    )
    thread.start()

    return {
        "status": "started",
        "query_id": search.id,
        "query_text": effective_query,
        "provider": search.provider,
    }


@router.get("/search-progress")
def get_search_progress(
    since: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Get real-time progress of the current Maps search."""
    with _maps_progress_lock:
        progress = dict(_maps_progress)

    with _maps_recently_lock:
        if since:
            recent = [r for r in _maps_recently_found if r.get("found_at", "") > since]
        else:
            recent = list(_maps_recently_found[-20:])

    progress["recently_found"] = recent
    if progress["total"] > 0:
        progress["percent"] = round(
            (progress["done"] + progress["failed"]) / progress["total"] * 100, 1
        )
    else:
        progress["percent"] = 0

    return progress


@router.get("/searches", response_model=MapSearchList)
def list_searches(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List past Maps search queries."""
    q = db.query(MapSearchQuery)

    if category:
        q = q.filter(MapSearchQuery.category == category)
    if city:
        q = q.filter(MapSearchQuery.city == city)
    if status:
        q = q.filter(MapSearchQuery.status == status)

    total = q.count()
    items = q.order_by(MapSearchQuery.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return MapSearchList(
        items=[MapSearchPublic.model_validate(i) for i in items],
        total=total, page=page, per_page=per_page,
    )


@router.get("/listings", response_model=BusinessListingList)
def list_listings(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search_query_id: Optional[int] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    has_email: Optional[bool] = None,
    has_phone: Optional[bool] = None,
    has_website: Optional[bool] = None,
    min_rating: Optional[float] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List business listings with filters."""
    q = db.query(BusinessListing)

    if search_query_id:
        q = q.filter(BusinessListing.search_query_id == search_query_id)
    if category:
        q = q.filter(BusinessListing.category.ilike(f"%{category}%"))
    if city:
        q = q.filter(BusinessListing.city.ilike(f"%{city}%"))
    if has_email:
        q = q.filter(BusinessListing.email.isnot(None), BusinessListing.email != "")
    if has_phone:
        q = q.filter(BusinessListing.phone.isnot(None), BusinessListing.phone != "")
    if has_website:
        q = q.filter(BusinessListing.website.isnot(None), BusinessListing.website != "")
    if min_rating is not None:
        q = q.filter(BusinessListing.rating >= min_rating)
    if search:
        q = q.filter(BusinessListing.business_name.ilike(f"%{search}%"))

    total = q.count()
    items = q.order_by(BusinessListing.id.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return BusinessListingList(
        items=[BusinessListingPublic.model_validate(i) for i in items],
        total=total, page=page, per_page=per_page,
    )


@router.get("/listings/export/csv")
def export_listings_csv(
    search_query_id: Optional[int] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    has_email: Optional[bool] = None,
    has_phone: Optional[bool] = None,
    limit: int = Query(5000, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export business listings as CSV."""
    q = db.query(BusinessListing)

    if search_query_id:
        q = q.filter(BusinessListing.search_query_id == search_query_id)
    if category:
        q = q.filter(BusinessListing.category.ilike(f"%{category}%"))
    if city:
        q = q.filter(BusinessListing.city.ilike(f"%{city}%"))
    if has_email:
        q = q.filter(BusinessListing.email.isnot(None), BusinessListing.email != "")
    if has_phone:
        q = q.filter(BusinessListing.phone.isnot(None), BusinessListing.phone != "")

    rows = q.order_by(BusinessListing.id.desc()).limit(limit).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Business Name", "Address", "City", "State", "Postcode",
        "Phone", "Email", "Website", "Rating", "Reviews", "Category",
    ])
    for r in rows:
        writer.writerow([
            r.business_name, r.address, r.city, r.state, r.postcode,
            r.phone, r.email, r.website, r.rating, r.reviews_count, r.category,
        ])

    output.seek(0)

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.export,
        description=f"Exported {len(rows)} business listings as CSV",
    ))
    db.commit()

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=business_listings.csv"},
    )


@router.get("/presets")
def get_presets(current_user: User = Depends(get_current_user)):
    """Return predefined Australian cities and business categories."""
    return {
        "categories": BUSINESS_CATEGORIES,
        "cities": AUSTRALIAN_CITIES,
    }
