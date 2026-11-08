from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import SoftDelete, TenantScoped, Timestamps, UUIDPk


class ApplicationStatus(str, enum.Enum):
    """Workflow statuses only — none of these represents an official licensing decision."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    AI_ANALYSIS = "AI_ANALYSIS"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    ADDITIONAL_INFORMATION_REQUIRED = "ADDITIONAL_INFORMATION_REQUIRED"
    APPROVED_FOR_NEXT_REVIEW_STAGE = "APPROVED_FOR_NEXT_REVIEW_STAGE"
    CLOSED = "CLOSED"


class ServiceCategory(str, enum.Enum):
    BNPL = "BNPL"
    DIGITAL_PAYMENTS = "DIGITAL_PAYMENTS"
    OPEN_BANKING = "OPEN_BANKING"
    LENDING = "LENDING"
    DIGITAL_WALLET = "DIGITAL_WALLET"


class FintechApplication(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "fintech_applications"
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    company_name_ar: Mapped[str] = mapped_column(String(200))
    company_name_en: Mapped[str] = mapped_column(String(200))
    commercial_registration: Mapped[str] = mapped_column(String(40), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    service_category: Mapped[ServiceCategory] = mapped_column(Enum(ServiceCategory, name="service_category"), index=True)
    business_model: Mapped[str] = mapped_column(Text, default="")
    target_customers: Mapped[str] = mapped_column(Text, default="")
    paid_up_capital_sar: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    expected_monthly_volume_sar: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    data_hosting_location: Mapped[str] = mapped_column(String(80), default="")
    uses_third_party_providers: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"), default=ApplicationStatus.DRAFT, index=True
    )
    assigned_analyst_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)

    assigned_analyst = relationship("User", foreign_keys=[assigned_analyst_id], lazy="joined")
    documents = relationship("ApplicationDocument", back_populates="application", lazy="selectin",
                             primaryjoin="and_(ApplicationDocument.application_id==FintechApplication.id, ApplicationDocument.deleted_at.is_(None))")


class DocumentType(str, enum.Enum):
    COMMERCIAL_REGISTRATION = "COMMERCIAL_REGISTRATION"
    BUSINESS_PLAN = "BUSINESS_PLAN"
    FINANCIAL_STATEMENTS = "FINANCIAL_STATEMENTS"
    AML_CTF_POLICY = "AML_CTF_POLICY"
    CYBERSECURITY_POLICY = "CYBERSECURITY_POLICY"
    DATA_PROTECTION_POLICY = "DATA_PROTECTION_POLICY"
    GOVERNANCE_STRUCTURE = "GOVERNANCE_STRUCTURE"
    OUTSOURCING_AGREEMENTS = "OUTSOURCING_AGREEMENTS"
    CONSUMER_PROTECTION_POLICY = "CONSUMER_PROTECTION_POLICY"
    RISK_MANAGEMENT_FRAMEWORK = "RISK_MANAGEMENT_FRAMEWORK"
    OTHER = "OTHER"


class ApplicationDocument(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "application_documents"
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fintech_applications.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, name="document_type"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(400))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[str] = mapped_column(String(30), default="PENDING")  # PENDING|PROCESSED|FAILED
    processing_error: Mapped[str] = mapped_column(Text, default="")
    scan_status: Mapped[str] = mapped_column(String(30), default="NOT_SCANNED")
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    application = relationship("FintechApplication", back_populates="documents")


class ApplicationComment(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "application_comments"
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fintech_applications.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30), default="COMMENT")  # COMMENT|INFO_REQUEST
    author = relationship("User", lazy="joined")


class ApplicationEvent(UUIDPk, Timestamps, TenantScoped, Base):
    """Application timeline (status changes, assignments, uploads)."""

    __tablename__ = "application_events"
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fintech_applications.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60))
    from_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    actor = relationship("User", lazy="joined")
