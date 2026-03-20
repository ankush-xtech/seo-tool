from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.middleware.deps import get_current_user
from app.models.models import Watchlist, Domain, User

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


@router.get("/")
def list_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's watchlist with domain details."""
    items = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id)
        .join(Domain, Watchlist.domain_id == Domain.id)
        .all()
    )
    result = []
    for item in items:
        domain = db.query(Domain).filter(Domain.id == item.domain_id).first()
        result.append({
            "id": item.id,
            "domain_id": item.domain_id,
            "notes": item.notes,
            "alert_on_score_change": item.alert_on_score_change,
            "score_threshold": item.score_threshold,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "domain": {
                "id": domain.id,
                "name": domain.name,
                "tld": domain.tld,
                "seo_score": domain.seo_score,
                "check_status": domain.check_status,
                "fetched_date": domain.fetched_date.isoformat() if domain.fetched_date else None,
            } if domain else None,
        })
    return result


@router.post("/{domain_id}")
def add_to_watchlist(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a domain to current user's watchlist."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.domain_id == domain_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already in watchlist")

    item = Watchlist(user_id=current_user.id, domain_id=domain_id)
    db.add(item)
    db.commit()
    return {"message": "Added to watchlist", "id": item.id}


@router.delete("/{watchlist_id}")
def remove_from_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an item from current user's watchlist."""
    item = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(item)
    db.commit()
    return {"message": "Removed from watchlist"}
