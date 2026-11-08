from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name_ar: str
    full_name_en: str
    title_ar: str
    title_en: str
    preferred_locale: str
    is_active: bool
    role_codes: list[str]
    org_id: uuid.UUID
    last_login_at: datetime | None = None


class MeOut(UserOut):
    permissions: list[str]
    organization: dict


class UserCreate(BaseModel):
    email: EmailStr
    full_name_ar: str = Field(min_length=2, max_length=200)
    full_name_en: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=10, max_length=200)
    roles: list[str] = Field(min_length=1)
    title_ar: str = ""
    title_en: str = ""


class UserUpdate(BaseModel):
    full_name_ar: str | None = None
    full_name_en: str | None = None
    roles: list[str] | None = None
    is_active: bool | None = None


class PrefsIn(BaseModel):
    preferred_locale: str = Field(pattern="^(ar|en)$")


class ApplicationIn(BaseModel):
    company_name_ar: str = Field(min_length=2, max_length=200)
    company_name_en: str = Field(min_length=2, max_length=200)
    commercial_registration: str = Field(default="", pattern=r"^(\d{10})?$")
    city: str = Field(default="", max_length=80)
    contact_email: EmailStr | None = None
    website: str = Field(default="", max_length=255)
    service_category: str = Field(pattern="^(BNPL|DIGITAL_PAYMENTS|OPEN_BANKING|LENDING|DIGITAL_WALLET)$")
    business_model: str = Field(default="", max_length=5000)
    target_customers: str = Field(default="", max_length=2000)
    paid_up_capital_sar: float | None = Field(default=None, ge=0, le=1e13)
    expected_monthly_volume_sar: float | None = Field(default=None, ge=0, le=1e14)
    data_hosting_location: str = Field(default="", max_length=80)
    uses_third_party_providers: bool = False


class ApplicationPatch(BaseModel):
    company_name_ar: str | None = Field(default=None, min_length=2, max_length=200)
    company_name_en: str | None = Field(default=None, min_length=2, max_length=200)
    commercial_registration: str | None = Field(default=None, pattern=r"^(\d{10})?$")
    city: str | None = None
    contact_email: EmailStr | None = None
    website: str | None = None
    service_category: str | None = Field(default=None, pattern="^(BNPL|DIGITAL_PAYMENTS|OPEN_BANKING|LENDING|DIGITAL_WALLET)$")
    business_model: str | None = Field(default=None, max_length=5000)
    target_customers: str | None = Field(default=None, max_length=2000)
    paid_up_capital_sar: float | None = Field(default=None, ge=0)
    expected_monthly_volume_sar: float | None = Field(default=None, ge=0)
    data_hosting_location: str | None = None
    uses_third_party_providers: bool | None = None


class TransitionIn(BaseModel):
    to_status: str
    reason: str = Field(default="", max_length=1000)


class AssignIn(BaseModel):
    analyst_id: uuid.UUID | None


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class DocumentOut(ORM):
    id: uuid.UUID
    application_id: uuid.UUID
    document_type: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    page_count: int
    processing_status: str
    processing_error: str
    scan_status: str
    created_at: datetime


class ApplicationOut(ORM):
    id: uuid.UUID
    reference: str
    company_name_ar: str
    company_name_en: str
    commercial_registration: str
    city: str
    contact_email: str
    website: str
    service_category: str
    business_model: str
    target_customers: str
    paid_up_capital_sar: float | None
    expected_monthly_volume_sar: float | None
    data_hosting_location: str
    uses_third_party_providers: bool
    status: str
    assigned_analyst_id: uuid.UUID | None
    assigned_analyst_name_ar: str | None = None
    assigned_analyst_name_en: str | None = None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    extracted_profile: dict
    is_synthetic: bool
    document_count: int = 0
    latest_risk: str | None = None
    allowed_transitions: list[str] = []


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    mode: str = Field(default="hybrid", pattern="^(hybrid|keyword|semantic)$")
    top_k: int = Field(default=8, ge=1, le=30)
    rerank: bool = False
    document_ids: list[uuid.UUID] = []
    version_id: uuid.UUID | None = None
    include_superseded: bool = False
    section: str = ""
    language: str = Field(default="", pattern="^(|ar|en)$")
    published_from: date | None = None
    published_to: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    tags: list[str] = []


class RagIn(SearchIn):
    locale: str = Field(default="ar", pattern="^(ar|en)$")


class RequirementIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    title_ar: str
    title_en: str
    description_ar: str = ""
    description_en: str = ""
    service_categories: list[str] = []
    required_document_types: list[str] = []
    rule: dict = {}
    severity: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    source_document_code: str = ""
    source_section: str = ""
    is_synthetic: bool = True
    active: bool = True


class RunIn(BaseModel):
    application_id: uuid.UUID


class DraftEditIn(BaseModel):
    summary_ar: str | None = None
    summary_en: str | None = None
    analyst_notes: str | None = None
    finding_updates: list[dict[str, Any]] = []
    new_findings: list[dict[str, Any]] = []


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(APPROVE_FOR_NEXT_STAGE|RETURN|REJECT|REQUEST_INFORMATION|COMMENT)$")
    comment: str = Field(default="", max_length=5000)
    confirmed: bool = False


class McpKeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["read"])


class AIConfigIn(BaseModel):
    provider: str = Field(pattern="^(mock|qwen|llama|openai_compatible)$")
    model: str = Field(default="", max_length=160)


class ModelIn(BaseModel):
    name: str
    provider: str = Field(pattern="^(mock|qwen|llama|openai_compatible)$")
    model_id: str
    version: str = ""
    purpose: str = Field(default="generation", pattern="^(generation|embedding)$")
    hosting: str = Field(default="hosted", pattern="^(hosted|self_hosted)$")
    base_url_env: str = Field(default="AI_BASE_URL", pattern=r"^[A-Z][A-Z0-9_]{1,79}$")
    context_window: int | None = None
    owner: str = ""
    approval_status: str = Field(default="PENDING", pattern="^(PENDING|APPROVED|REJECTED|RETIRED)$")
    deployment_status: str = Field(default="NOT_DEPLOYED", pattern="^(NOT_DEPLOYED|STAGING|PRODUCTION)$")
    notes: str = ""


class ModelPatch(BaseModel):
    approval_status: str | None = Field(default=None, pattern="^(PENDING|APPROVED|REJECTED|RETIRED)$")
    deployment_status: str | None = Field(default=None, pattern="^(NOT_DEPLOYED|STAGING|PRODUCTION)$")
    owner: str | None = None
    notes: str | None = None


class UseCaseIn(BaseModel):
    code: str
    name_ar: str
    name_en: str
    business_purpose_ar: str = ""
    business_purpose_en: str = ""
    owner: str = ""
    model_id: uuid.UUID | None = None
    risk_classification: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    data_classification: str = "CONFIDENTIAL"
    human_oversight: str = "HUMAN_IN_THE_LOOP"
    approval_status: str = "PENDING"
    deployment_status: str = "NOT_DEPLOYED"
    monitoring_status: str = "NOT_MONITORED"
    control_mappings: list[dict] = []


class UseCasePatch(BaseModel):
    approval_status: str | None = Field(default=None, pattern="^(PENDING|APPROVED|REJECTED|RETIRED)$")
    deployment_status: str | None = Field(default=None, pattern="^(NOT_DEPLOYED|STAGING|PRODUCTION)$")
    monitoring_status: str | None = Field(default=None, pattern="^(MONITORED|DEGRADED|NOT_MONITORED)$")
    risk_classification: str | None = Field(default=None, pattern="^(LOW|MEDIUM|HIGH)$")
    control_mappings: list[dict] | None = None
    owner: str | None = None
