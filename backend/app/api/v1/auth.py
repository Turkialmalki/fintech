from __future__ import annotations

import uuid
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import RequestCtx, get_principal, request_ctx, require
from app.core.config import settings
from app.core.db import get_db
from app.core.errors import AppError, Conflict, NotFound, RateLimited, Unauthorized
from app.core.ratelimit import limiter
from app.core.security import ROLES, Principal, create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models import Role, User
from app.schemas.common import LoginIn, MeOut, PrefsIn, RefreshIn, TokenOut, UserCreate, UserOut, UserUpdate
from app.services import audit

router = APIRouter(tags=["auth"])
_DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


def _tokens(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id, user.org_id), refresh_token=create_refresh_token(user.id, user.org_id),
                    expires_in=settings.access_token_minutes * 60)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db), rc: RequestCtx = Depends(request_ctx)):
    if not limiter.hit(f"login:{rc.ip or 'local'}:{body.email.lower()}", settings.login_rate_limit_per_minute):
        audit.record_isolated(category="AUTH", action="login_rate_limited", outcome="DENIED", details={"email": body.email}, ip=rc.ip)
        raise RateLimited()
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.deleted_at.is_(None)))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        audit.record_isolated(category="AUTH", action="login_failed", outcome="FAILURE", org_id=user.org_id if user else None,
                              details={"email": body.email}, ip=rc.ip, request_id=rc.request_id)
        raise Unauthorized("Invalid email or password", "البريد الإلكتروني أو كلمة المرور غير صحيحة")
    user.last_login_at = datetime.now(timezone.utc)
    audit.record(db, category="AUTH", action="login_succeeded", org_id=user.org_id, actor_id=user.id, actor_type="USER", ip=rc.ip,
                 request_id=rc.request_id)
    return _tokens(user)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise Unauthorized("Invalid refresh token", "رمز التحديث غير صالح")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active or str(user.org_id) != payload["org"]:
        raise Unauthorized()
    return _tokens(user)


@router.post("/auth/logout", status_code=204)
def logout(p: Principal = Depends(get_principal), db: Session = Depends(get_db), rc: RequestCtx = Depends(request_ctx)):
    audit.record(db, category="AUTH", action="logout", principal=p, ip=rc.ip)


def me_payload(user: User) -> MeOut:
    return MeOut(**UserOut.model_validate(user).model_dump(), permissions=sorted(user.permission_codes),
                 organization={"id": str(user.organization.id), "name_ar": user.organization.name_ar,
                               "name_en": user.organization.name_en, "is_synthetic": user.organization.is_synthetic})


@router.get("/auth/me", response_model=MeOut)
def me(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return me_payload(db.get(User, p.user_id))


@router.patch("/auth/me/preferences", response_model=MeOut)
def prefs(body: PrefsIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    u = db.get(User, p.user_id)
    u.preferred_locale = body.preferred_locale
    return me_payload(u)


# ---- users (tenant-scoped) --------------------------------------------------------------
@router.get("/users", response_model=list[UserOut], tags=["users"])
def list_users(p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.org_id == p.org_id, User.deleted_at.is_(None)).order_by(User.full_name_en)).all()


def _roles(db: Session, codes: list[str]) -> list[Role]:
    bad = [c for c in codes if c not in ROLES]
    if bad:
        raise AppError("Unknown role", "دور غير معروف", status_code=422, details={"roles": bad})
    return list(db.scalars(select(Role).where(Role.code.in_(codes))).all())


@router.post("/users", response_model=UserOut, status_code=201, tags=["users"])
def create_user(body: UserCreate, p: Principal = Depends(require("users:manage")), db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise Conflict("Email already registered", "البريد الإلكتروني مسجل مسبقاً")
    u = User(org_id=p.org_id, email=body.email.lower(), full_name_ar=body.full_name_ar, full_name_en=body.full_name_en,
             title_ar=body.title_ar, title_en=body.title_en, password_hash=hash_password(body.password), roles=_roles(db, body.roles))
    db.add(u)
    db.flush()
    audit.record(db, category="SETTINGS", action="user_created", principal=p, resource_type="user", resource_id=u.id,
                 details={"roles": body.roles})
    return u


@router.patch("/users/{user_id}", response_model=UserOut, tags=["users"])
def update_user(user_id: uuid.UUID, body: UserUpdate, p: Principal = Depends(require("users:manage")), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.org_id != p.org_id:
        raise NotFound("User", "المستخدم")
    if body.roles is not None:
        if u.id == p.user_id and "admin" not in body.roles:
            raise AppError("You cannot remove your own admin role", "لا يمكنك إزالة صلاحية المدير عن حسابك", status_code=422)
        u.roles = _roles(db, body.roles)
    for f in ("full_name_ar", "full_name_en", "is_active"):
        if getattr(body, f) is not None:
            setattr(u, f, getattr(body, f))
    audit.record(db, category="SETTINGS", action="user_updated", principal=p, resource_type="user", resource_id=u.id,
                 details=body.model_dump(exclude_none=True))
    return u
