"""Audit trail writer. Sensitive values are redacted before persistence."""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models import AuditLog

log = logging.getLogger("rip.audit")

_SENSITIVE_KEYS = re.compile(r"(password|secret|token|api[_-]?key|authorization)", re.I)
_EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_IBAN = re.compile(r"\bSA\d{2}[0-9A-Z]{20}\b")
_NATIONAL_ID = re.compile(r"\b[12]\d{9}\b")


def redact_text(value: str) -> str:
    value = _EMAIL.sub(r"\1***\2", value)
    value = _IBAN.sub("SA**[REDACTED-IBAN]", value)
    value = _NATIONAL_ID.sub("[REDACTED-ID]", value)
    return value


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if _SENSITIVE_KEYS.search(str(k)) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj[:50]]
    if isinstance(obj, str):
        return redact_text(obj[:2000])
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return redact_text(str(obj)[:500])


def record(
    db: Session,
    *,
    category: str,
    action: str,
    principal: Principal | None = None,
    org_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    actor_type: str | None = None,
    resource_type: str = "",
    resource_id: str | uuid.UUID = "",
    outcome: str = "SUCCESS",
    details: dict | None = None,
    ip: str | None = None,
    request_id: str = "",
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id or (principal.org_id if principal else None),
        actor_id=actor_id or (principal.user_id if principal else None),
        actor_type=actor_type or (principal.actor_type if principal else "SYSTEM"),
        category=category,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        outcome=outcome,
        details=redact(details or {}),
        ip_address=ip,
        request_id=request_id,
    )
    db.add(entry)
    db.flush()
    return entry


def record_isolated(**kwargs) -> None:
    """Write an audit entry in its own transaction (survives a rollback of the caller)."""
    from app.core.db import session_scope

    try:
        with session_scope() as db:
            record(db, **kwargs)
    except Exception:  # never let auditing failures hide the original error, but log them
        log.exception("failed to write isolated audit record")
