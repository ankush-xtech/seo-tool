from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import verify_access_token
from app.models.models import User, UserRole

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: returns the authenticated User from JWT bearer token."""
    payload = verify_access_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency alias — same as get_current_user, kept for explicitness."""
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: allows only admin role. Use on admin-only routes."""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def require_verified(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: allows only verified accounts."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    return current_user
