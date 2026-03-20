from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status, Request
from typing import Optional

from app.models.models import User, RefreshToken, AuditLog, AuditAction, UserRole
from app.schemas.auth import UserCreate, LoginRequest
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, verify_refresh_token
)
from app.core.config import settings


class AuthService:

    @staticmethod
    def register_user(db: Session, data: UserCreate) -> User:
        """Create a new user. Raises 400 if email already exists."""
        existing = db.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        user = User(
            email=data.email,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        """Verify credentials. Returns user or raises 401."""
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact an administrator."
            )
        return user

    @staticmethod
    def create_tokens(db: Session, user: User, request: Optional[Request] = None) -> dict:
        """Generate access + refresh tokens, store refresh token in DB."""
        token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Persist refresh token
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db_token = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
        )
        db.add(db_token)

        # Update last login
        user.last_login = datetime.now(timezone.utc)

        # Audit log
        audit = AuditLog(
            user_id=user.id,
            action=AuditAction.login,
            description=f"User logged in: {user.email}",
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )
        db.add(audit)
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> dict:
        """Exchange valid refresh token for a new access token."""
        payload = verify_refresh_token(refresh_token)
        user_id = int(payload["sub"])

        # Check token exists and is not revoked
        db_token = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == refresh_token,
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
            )
            .first()
        )
        if not db_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or revoked"
            )
        if db_token.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired"
            )

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
        new_access_token = create_access_token(token_data)
        return {"access_token": new_access_token, "token_type": "bearer"}

    @staticmethod
    def logout_user(db: Session, refresh_token: str, user_id: int) -> None:
        """Revoke refresh token on logout."""
        db_token = (
            db.query(RefreshToken)
            .filter(RefreshToken.token == refresh_token, RefreshToken.user_id == user_id)
            .first()
        )
        if db_token:
            db_token.is_revoked = True
            db.add(AuditLog(
                user_id=user_id,
                action=AuditAction.logout,
                description="User logged out"
            ))
            db.commit()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
