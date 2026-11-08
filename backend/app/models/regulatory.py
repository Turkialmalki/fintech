from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Computed, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.core.db import Base
from app.models.base import SoftDelete, TenantScoped, Timestamps, UUIDPk
from app.models.vector import EmbeddingVector


class RegulatoryDocument(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    __tablename__ = "regulatory_documents"
    __table_args__ = (UniqueConstraint("org_id", "document_code", name="uq_regdoc_org_code"),)
    document_code: Mapped[str] = mapped_column(String(60), index=True)
    title_ar: Mapped[str] = mapped_column(String(400), default="")
    title_en: Mapped[str] = mapped_column(String(400), default="")
    source: Mapped[str] = mapped_column(String(300), default="")
    language: Mapped[str] = mapped_column(String(8), default="ar")  # ar | en | mixed
    # Access level for permission-aware retrieval: public | internal | restricted
    classification: Mapped[str] = mapped_column(String(20), default="internal", index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    versions = relationship(
        "RegulatoryDocumentVersion", back_populates="document", lazy="selectin",
        order_by="RegulatoryDocumentVersion.version_number.desc()",
    )


class RegulatoryDocumentVersion(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "regulatory_document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_regdoc_version"),)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    version_label: Mapped[str] = mapped_column(String(40), default="")
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # only when supplied
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # only when supplied
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE | SUPERSEDED
    filename: Mapped[str] = mapped_column(String(255), default="")
    content_type: Mapped[str] = mapped_column(String(120), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    storage_key: Mapped[str] = mapped_column(String(400), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexing_status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|INDEXED|FAILED
    indexing_error: Mapped[str] = mapped_column(Text, default="")
    extracted_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    document = relationship("RegulatoryDocument", back_populates="versions")


class RegulatoryChunk(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "regulatory_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id", ondelete="CASCADE"), index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_document_versions.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(300), default="")
    language: Mapped[str] = mapped_column(String(8), default="ar")
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    search_vector = deferred(mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', coalesce(normalized_text, ''))", persisted=True)
    ))
    document = relationship("RegulatoryDocument", lazy="joined")
    version = relationship("RegulatoryDocumentVersion", lazy="joined")

    __table_args__ = (Index("ix_regchunk_search", "search_vector", postgresql_using="gin"),)


class Embedding(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "embeddings"
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_chunks.id", ondelete="CASCADE"), index=True, unique=True
    )
    provider: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(120))
    dim: Mapped[int] = mapped_column(Integer)
    # pgvector `vector(dim)` when the extension exists, float8[] otherwise (see migration 0001).
    vector = deferred(mapped_column(EmbeddingVector))


class RegulatoryRequirement(UUIDPk, Timestamps, SoftDelete, TenantScoped, Base):
    """Configured (synthetic demo) requirement used by deterministic gap checks.

    Requirements are configuration, linked to the document section they were taken from.
    The platform never invents them; administrators maintain them.
    """

    __tablename__ = "regulatory_requirements"
    __table_args__ = (UniqueConstraint("org_id", "code", name="uq_requirement_org_code"),)
    code: Mapped[str] = mapped_column(String(40))
    title_ar: Mapped[str] = mapped_column(String(300))
    title_en: Mapped[str] = mapped_column(String(300))
    description_ar: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    service_categories: Mapped[list[str]] = mapped_column(JSONB, default=list)  # empty = all
    required_document_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Optional structured rule e.g. {"field": "paid_up_capital_sar", "op": ">=", "value": 5000000}
    rule: Mapped[dict] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    source_document_code: Mapped[str] = mapped_column(String(60), default="")
    source_section: Mapped[str] = mapped_column(String(300), default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
