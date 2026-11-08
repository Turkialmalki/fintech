from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import SoftDelete, TenantScoped, Timestamps, UUIDPk


class AgentRun(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "agent_runs"
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fintech_applications.id", ondelete="CASCADE"), index=True, nullable=True
    )
    workflow: Mapped[str] = mapped_column(String(60), default="fintech_assessment")
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)  # QUEUED|RUNNING|SUCCEEDED|FAILED|AWAITING_REVIEW
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    ai_provider: Mapped[str] = mapped_column(String(40), default="")
    ai_model: Mapped[str] = mapped_column(String(120), default="")
    tool_transport: Mapped[str] = mapped_column(String(30), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    budget: Mapped[dict] = mapped_column(JSONB, default=dict)
    final_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    steps = relationship("AgentStep", lazy="selectin", order_by="AgentStep.sequence")
    triggered_by = relationship("User", lazy="joined")


class AgentStep(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "agent_steps"
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(60))
    step_type: Mapped[str] = mapped_column(String(30))  # NODE|TOOL_CALL|LLM_CALL|DECISION|ERROR
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="OK")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[dict] = mapped_column(JSONB, default=dict)
    output: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)


class AssessmentDraft(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "assessment_drafts"
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fintech_applications.id", ondelete="CASCADE"), index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_drafts.id"), nullable=True)
    # DRAFT | PENDING_REVIEW | RETURNED | APPROVED_FOR_NEXT_STAGE | REJECTED | SUPERSEDED
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    authored_by: Mapped[str] = mapped_column(String(10), default="AI")  # AI | HUMAN | MIXED
    edited_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    summary_ar: Mapped[str] = mapped_column(Text, default="")
    summary_en: Mapped[str] = mapped_column(Text, default="")
    analyst_notes: Mapped[str] = mapped_column(Text, default="")
    limitations_ar: Mapped[str] = mapped_column(Text, default="")
    limitations_en: Mapped[str] = mapped_column(Text, default="")
    overall_risk: Mapped[str] = mapped_column(String(20), default="UNDETERMINED")
    extracted_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    missing_documents: Mapped[list] = mapped_column(JSONB, default=list)
    generation_meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    findings = relationship("AssessmentFinding", lazy="selectin", order_by="AssessmentFinding.sequence",
                            primaryjoin="and_(AssessmentFinding.draft_id==AssessmentDraft.id, AssessmentFinding.deleted_at.is_(None))")
    edited_by = relationship("User", lazy="joined")


class AssessmentFinding(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "assessment_findings"
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_drafts.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    # REGULATORY | RISK | GAP | MISSING_INFORMATION | OBSERVATION
    category: Mapped[str] = mapped_column(String(30), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")  # LOW|MEDIUM|HIGH|CRITICAL|INFO
    title_ar: Mapped[str] = mapped_column(String(400))
    title_en: Mapped[str] = mapped_column(String(400))
    evidence_ar: Mapped[str] = mapped_column(Text, default="")  # factual: what the documents/application say
    evidence_en: Mapped[str] = mapped_column(Text, default="")
    interpretation_ar: Mapped[str] = mapped_column(Text, default="")  # model/analyst interpretation
    interpretation_en: Mapped[str] = mapped_column(Text, default="")
    uncertainty: Mapped[str] = mapped_column(Text, default="")
    source_agent: Mapped[str] = mapped_column(String(60), default="")
    origin: Mapped[str] = mapped_column(String(20), default="RULE")  # RULE | AI | HUMAN
    requirement_code: Mapped[str] = mapped_column(String(40), default="")
    analyst_status: Mapped[str] = mapped_column(String(20), default="UNREVIEWED")  # UNREVIEWED|CONFIRMED|DISMISSED|EDITED
    citations = relationship("AssessmentCitation", lazy="selectin")


class AssessmentCitation(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "assessment_citations"
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_findings.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regulatory_chunks.id", ondelete="SET NULL"), nullable=True)
    application_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_documents.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(30), default="REGULATORY")  # REGULATORY | APPLICATION_DOCUMENT | APPLICATION_FIELD
    document_code: Mapped[str] = mapped_column(String(60), default="")
    document_title: Mapped[str] = mapped_column(String(400), default="")
    version_label: Mapped[str] = mapped_column(String(40), default="")
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(300), default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(default=False)  # citation validator result


class AnalystReview(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "analyst_reviews"
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_drafts.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fintech_applications.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # APPROVE_FOR_NEXT_STAGE | RETURN | REJECT | REQUEST_INFORMATION | COMMENT
    decision: Mapped[str] = mapped_column(String(40))
    comment: Mapped[str] = mapped_column(Text, default="")
    confirmed: Mapped[bool] = mapped_column(default=False)
    reviewer = relationship("User", lazy="joined")
