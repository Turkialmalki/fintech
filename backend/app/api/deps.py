from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.security import Principal, decode_token
from app.models import User
from app.services import audit

bearer = HTTPBearer(auto_error=False)


@dataclass
class RequestCtx:
    ip: str | None
    request_id: str


def request_ctx(request: Request) -> RequestCtx:
    ip = request.client.host if request.client else None
    if ip in ("testclient", "testserver"):
        ip = None
    return RequestCtx(ip=ip, request_id=getattr(request.state, "request_id", ""))


def principal_from_user(user: User, actor_type: str = "USER", scopes: frozenset[str] = frozenset()) -> Principal:
    return Principal(
        user_id=user.id, org_id=user.org_id, email=user.email, roles=tuple(user.role_codes),
        permissions=frozenset(user.permission_codes), actor_type=actor_type, scopes=scopes,
    )


def get_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized()
    try:
        payload = decode_token(creds.credentials, "access")
        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise Unauthorized("Invalid or expired token", "انتهت صلاحية الجلسة أو أن الرمز غير صالح")
    user = db.get(User, user_id)
    # tenant binding: the token's org must still match the user's org
    if user is None or not user.is_active or user.deleted_at is not None or user.org_id != org_id:
        raise Unauthorized("User is not active", "الحساب غير نشط")
    return principal_from_user(user)


def require(*perms: str):
    def dep(request: Request, principal: Principal = Depends(get_principal)) -> Principal:
        missing = [p for p in perms if not principal.has(p)]
        if missing:
            audit.record_isolated(
                category="AUTH", action="permission_denied", principal=principal, outcome="DENIED",
                resource_type="route", resource_id=request.url.path, details={"missing": missing},
                request_id=getattr(request.state, "request_id", ""),
            )
            raise Forbidden(details={"missing_permissions": missing})
        return principal

    return dep
