export type Me = {
  id: string; email: string; full_name_ar: string; full_name_en: string; title_ar: string; title_en: string;
  preferred_locale: "ar" | "en"; role_codes: string[]; permissions: string[]; org_id: string;
  organization: { id: string; name_ar: string; name_en: string; is_synthetic: boolean };
};

export type Application = {
  id: string; reference: string; company_name_ar: string; company_name_en: string; commercial_registration: string; city: string;
  contact_email: string; website: string; service_category: string; business_model: string; target_customers: string;
  paid_up_capital_sar: number | null; expected_monthly_volume_sar: number | null; data_hosting_location: string;
  uses_third_party_providers: boolean; status: string; assigned_analyst_id: string | null; assigned_analyst_name_ar: string | null;
  assigned_analyst_name_en: string | null; submitted_at: string | null; created_at: string; updated_at: string;
  extracted_profile: Record<string, unknown>; is_synthetic: boolean; document_count: number; latest_risk: string | null; allowed_transitions: string[];
};

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type AppDocument = {
  id: string; application_id: string; document_type: string; filename: string; content_type: string; size_bytes: number; sha256: string;
  page_count: number; processing_status: string; processing_error: string; scan_status: string; created_at: string;
};

export type Citation = {
  id: string; source_type: string; chunk_id: string | null; application_document_id: string | null; document_code: string; document_title: string;
  version_label: string; page_number: number | null; section: string; quote: string; score: number; verified: boolean;
};

export type Finding = {
  id: string; sequence: number; category: string; severity: string; title_ar: string; title_en: string; evidence_ar: string; evidence_en: string;
  interpretation_ar: string; interpretation_en: string; uncertainty: string; source_agent: string; origin: string; requirement_code: string;
  analyst_status: string; citations: Citation[];
};

export type Review = { id: string; decision: string; comment: string; confirmed: boolean; created_at: string; reviewer_name_ar: string; reviewer_name_en: string; draft_id: string };

export type Draft = {
  id: string; application_id: string; agent_run_id: string | null; version: number; parent_id: string | null; status: string; authored_by: string;
  edited_by_name_ar: string | null; edited_by_name_en: string | null; summary_ar: string; summary_en: string; analyst_notes: string;
  limitations_ar: string; limitations_en: string; overall_risk: string; extracted_profile: Record<string, unknown>;
  missing_documents: { document_type: string; requirement_codes: string[] }[]; generation_meta: Record<string, any>; created_at: string;
  findings: Finding[]; application: Application; reviews: Review[]; versions: { id: string; version: number; status: string; authored_by: string; created_at: string }[];
};

export type Hit = {
  chunk_id: string; document_id: string; document_code: string; title_ar: string; title_en: string; source: string; classification: string;
  is_synthetic: boolean; version_id: string; version_label: string; version_status: string; publication_date: string | null; effective_date: string | null;
  page_number: number | null; section: string; text: string; score: number; keyword_score: number; vector_score: number;
};

export type Run = {
  id: string; application_id: string | null; status: string; ai_provider: string; ai_model: string; tool_transport: string; started_at: string | null;
  finished_at: string | null; duration_ms: number; step_count: number; tool_call_count: number; tokens_in: number; tokens_out: number; cost_usd: number;
  error: string; budget: Record<string, number>; final_state: Record<string, any>; created_at: string; triggered_by_name_ar: string | null;
  triggered_by_name_en: string | null; application_reference?: string; company_name_ar?: string; company_name_en?: string;
  steps?: { id: string; sequence: number; agent: string; step_type: string; name: string; status: string; attempt: number; duration_ms: number;
    input: any; output: any; error: string; tokens_in: number; tokens_out: number; created_at: string }[];
};

export type User = { id: string; email: string; full_name_ar: string; full_name_en: string; title_ar: string; title_en: string; role_codes: string[]; is_active: boolean };
