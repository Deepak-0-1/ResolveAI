"""Registration, login, and current-user endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from resolveai_api.deps import get_current_user
from resolveai_api.schemas import TokenResponse, UserCreate, UserLogin, UserOut
from resolveai_db.models import AuditLog, User, UserRole
from resolveai_db.security import create_access_token, hash_password, verify_password
from resolveai_db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: Session = Depends(get_db)) -> User:
    """Public self-registration always creates a customer (not admin)."""
    existing = db.query(User).filter(User.email == body.email.lower()).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.customer,
    )
    db.add(user)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="user.register",
            resource_type="user",
            resource_id=user.id,
            detail={"email": user.email},
        )
    )
    db.flush()
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower()).one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(subject=user.id, role=user.role.value, email=user.email)
    db.add(
        AuditLog(
            user_id=user.id,
            action="user.login",
            resource_type="user",
            resource_id=user.id,
        )
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
