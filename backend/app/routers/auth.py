from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.middleware.deps import get_current_user
from app.schemas.auth import (
    LoginRequest, LoginResponse, UserCreate, UserPublic,
    RefreshRequest, TokenResponse, SuccessResponse, ChangePasswordRequest
)
from app.services.auth_service import AuthService
from app.core.security import hash_password, verify_password
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    user = AuthService.register_user(db, data)
    return user


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate and return JWT tokens."""
    user = AuthService.authenticate_user(db, data.email, data.password)
    tokens = AuthService.create_tokens(db, user, request)
    return {**tokens, "user": user}


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    return AuthService.refresh_access_token(db, data.refresh_token)


@router.post("/logout", response_model=SuccessResponse)
def logout(
    data: RefreshRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke the refresh token to log out."""
    AuthService.logout_user(db, data.refresh_token, current_user.id)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@router.put("/change-password", response_model=SuccessResponse)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the current user's password."""
    if not verify_password(data.current_password, current_user.hashed_password):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}
