from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import SoftDelete, TenantScoped, Timestamps, UUIDPk


class AIModel(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "ai_models"
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(40))  # qwen | llama | openai_compatible | mock
    model_id: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(60), default="")
    purpose: Mapped[str] = mapped_column(String(30), default="generation")  # generation | embedding
    hosting: Mapped[str] = mapped_column(String(30), default="hosted")  # hosted | self_hosted
    base_url_env: Mapped[str] = mapped_column(String(80), default="AI_BASE_URL")  # name of env var, never the secret
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSONB, default=dict)  # probed capabilities
    capabilities_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[str] = mapped_column(String(160), default="")
    approval_status: Mapped[str] = mapped_column(String(30), default="PENDING")  # PENDING|APPROVED|REJECTED|RETIRED
    deployment_status: Mapped[str] = mapped_column(String(30), default="NOT_DEPLOYED")  # NOT_DEPLOYED|STAGING|PRODUCTION
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class AIUseCase(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "ai_use_cases"
    code: Mapped[str] = mapped_column(String(40))
    name_ar: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    business_purpose_ar: Mapped[str] = mapped_column(Text, default="")
    business_purpose_en: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(160), default="")
    model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_models.id"), nullable=True)
    risk_classification: Mapped[str] = mapped_column(String(20), default="MEDIUM")  # LOW|MEDIUM|HIGH
    data_classification: Mapped[str] = mapped_column(String(30), default="CONFIDENTIAL")
    human_oversight: Mapped[str] = mapped_column(String(60), default="HUMAN_IN_THE_LOOP")
    approval_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    deployment_status: Mapped[str] = mapped_column(String(30), default="NOT_DEPLOYED")
    monitoring_status: Mapped[str] = mapped_column(String(30), default="NOT_MONITORED")  # MONITORED|DEGRADED|NOT_MONITORED
    control_mappings: Mapped[list] = mapped_column(JSONB, default=list)  # [{framework, control_ref, status, note}]
    model = relationship("AIModel", lazy="joined")


class GovernanceControl(UUIDPk, Timestamps, TenantScoped, Base):
    """Configurable framework reference areas. Review aids — never evidence of legal compliance."""

    __tablename__ = "governance_controls"
    framework: Mapped[str] = mapped_column(String(60), index=True)  # NIST_AI_RMF | ISO_IEC_42001 | SA_DATA_PROTECTION | FS_CYBER_TECH
    reference: Mapped[str] = mapped_column(String(60))
    title_ar: Mapped[str] = mapped_column(String(300))
    title_en: Mapped[str] = mapped_column(String(300))
    description_ar: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    is_reference_summary: Mapped[bool] = mapped_column(Boolean, default=True)


class ModelEvaluation(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "model_evaluations"
    model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_models.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(160))
    dataset: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(8), default="mixed")
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[list] = mapped_column(JSONB, default=list)
    run_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class AuditLog(UUIDPk, Timestamps, Base):
    """Append-only audit trail. org_id nullable for pre-auth events (failed logins)."""

    __tablename__ = "audit_logs"
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="USER")  # USER | AGENT | MCP_CLIENT | SYSTEM
    category: Mapped[str] = mapped_column(String(40), index=True)  # AUTH|APPLICATION|DOCUMENT|RETRIEVAL|MODEL|AGENT|MCP|REVIEW|GOVERNANCE|SETTINGS
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(60), default="")
    resource_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    outcome: Mapped[str] = mapped_column(String(20), default="SUCCESS")  # SUCCESS | FAILURE | DENIED
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    actor = relationship("User", lazy="joined")


class ModelInvocation(UUIDPk, Timestamps, Base):
    """Telemetry for each LLM / embedding call (latency, tokens, cost)."""

    __tablename__ = "model_invocations"
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(160))
    operation: Mapped[str] = mapped_column(String(30))  # chat | json | embed
    purpose: Mapped[str] = mapped_column(String(60), default="")
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")


class RequestMetric(UUIDPk, Base):
    __tablename__ = "request_metrics"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    method: Mapped[str] = mapped_column(String(10))
    route: Mapped[str] = mapped_column(String(200), index=True)
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
