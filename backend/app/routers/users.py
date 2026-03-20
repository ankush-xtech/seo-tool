from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.middleware.deps import get_current_user, require_admin
from app.models.models import User, UserRole, AuditLog, AuditAction
from app.schemas.auth import UserPublic, UserCreate, UserUpdate, UserList, SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=UserList, dependencies=[Depends(require_admin)])
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Admin: list all users with optional filters."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        query = query.filter(
            User.email.contains(search) | User.full_name.contains(search)
        )

    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()

    return {"users": users, "total": total, "page": page, "per_page": per_page}


@router.post("/", response_model=UserPublic, status_code=201, dependencies=[Depends(require_admin)])
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: create a new team member."""
    user = AuthService.register_user(db, data)
    db.add(AuditLog(
        user_id=admin.id,
        action=AuditAction.user_created,
        description=f"Admin created user: {user.email}",
        meta={"new_user_id": user.id, "role": data.role}
    ))
    db.commit()
    return user


@router.get("/{user_id}", response_model=UserPublic, dependencies=[Depends(require_admin)])
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Admin: get a specific user by ID."""
    return AuthService.get_user_by_id(db, user_id)


@router.put("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user. Admin can update any user; regular users can only update themselves."""
    if current_user.role != UserRole.admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    user = AuthService.get_user_by_id(db, user_id)

    # Only admin can change roles
    if data.role and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can change user roles")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)

    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.user_updated,
        description=f"Updated user: {user.email}",
        meta=data.model_dump(exclude_none=True)
    ))
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=SuccessResponse, dependencies=[Depends(require_admin)])
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: deactivate (soft-delete) a user."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user = AuthService.get_user_by_id(db, user_id)
    user.is_active = False

    db.add(AuditLog(
        user_id=admin.id,
        action=AuditAction.user_deleted,
        description=f"Deactivated user: {user.email}"
    ))
    db.commit()
    return {"message": f"User {user.email} has been deactivated"}
