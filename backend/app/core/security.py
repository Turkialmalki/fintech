"""Authentication primitives and the RBAC permission catalogue.

Authorization is always decided here, deterministically, from the authenticated principal.
No model output is ever consulted for an authorization decision.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# ---- permission catalogue -------------------------------------------------------------
PERMISSIONS: dict[str, str] = {
    "applications:read": "View fintech applications",
    "applications:write": "Create and edit fintech applications",
    "applications:assign": "Assign analysts to applications",
    "documents:upload": "Upload application documents",
    "regulatory:read": "Search and read regulatory documents",
    "regulatory:read_restricted": "Read restricted regulatory documents",
    "regulatory:manage": "Upload and manage regulatory documents and requirements",
    "assessments:run": "Run AI assessments",
    "assessments:read": "View assessments",
    "reviews:write": "Edit drafts and record review decisions",
    "reviews:approve": "Approve drafts for the next review stage",
    "audit:read": "Read audit history",
    "governance:read": "View AI governance registry",
    "governance:manage": "Manage AI governance registry and model configuration",
    "users:manage": "Manage users",
    "settings:manage": "Manage system settings",
    "mcp:manage": "Manage MCP API keys",
}

ROLES: dict[str, dict] = {
    "admin": {"ar": "مدير النظام", "en": "System administrator", "perms": list(PERMISSIONS)},
    "supervisor": {
        "ar": "مشرف المراجعة", "en": "Review supervisor",
        "perms": ["applications:read", "applications:write", "applications:assign", "documents:upload",
                  "regulatory:read", "regulatory:read_restricted", "assessments:run", "assessments:read",
                  "reviews:write", "reviews:approve", "audit:read", "governance:read", "mcp:manage"],
    },
    "analyst": {
        "ar": "محلل", "en": "Analyst",
        "perms": ["applications:read", "applications:write", "documents:upload", "regulatory:read",
                  "assessments:run", "assessments:read", "reviews:write", "governance:read"],
    },
    "auditor": {
        "ar": "مدقق", "en": "Auditor",
        "perms": ["applications:read", "regulatory:read", "assessments:read", "audit:read", "governance:read"],
    },
    "viewer": {"ar": "مطّلع", "en": "Viewer", "perms": ["applications:read", "regulatory:read", "assessments:read"]},
}


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    org_id: uuid.UUID
    email: str
    roles: tuple[str, ...]
    permissions: frozenset[str]
    actor_type: str = "USER"  # USER | MCP_CLIENT | AGENT
    scopes: frozenset[str] = field(default_factory=frozenset)  # MCP key scopes

    def has(self, perm: str) -> bool:
        return perm in self.permissions

    @property
    def can_read_restricted(self) -> bool:
        return "regulatory:read_restricted" in self.permissions

    def allowed_classifications(self) -> list[str]:
        levels = ["public", "internal"]
        if self.can_read_restricted:
            levels.append("restricted")
        return levels


# ---- passwords ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# ---- JWT ------------------------------------------------------------------------------------
def _encode(payload: dict, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    body = {**payload, "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp()), "jti": secrets.token_hex(8)}
    return jwt.encode(body, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    return _encode({"sub": str(user_id), "org": str(org_id), "typ": "access"}, timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    return _encode({"sub": str(user_id), "org": str(org_id), "typ": "refresh"}, timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: str = "access") -> dict:
    payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_algorithm],
                         options={"require": ["exp", "sub", "org", "typ"]})
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# ---- MCP API keys ------------------------------------------------------------------------
def generate_api_key() -> tuple[str, str, str]:
    raw = "rip_" + secrets.token_urlsafe(32)
    return raw, raw[:12], hash_api_key(raw)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
