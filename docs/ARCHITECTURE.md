# Architecture

```
 Browser (Arabic RTL / English LTR)
   │  same-origin /api/v1 (Next.js rewrite)
 ┌─▼──────────────┐      ┌──────────────────────────── API (FastAPI) ─────────────────────────────┐
 │  Next.js web   │─────▶│ auth · RBAC · tenancy · applications · documents · regulatory · RAG     │
 └────────────────┘      │ assessments · reviews · governance · audit · observability · PDFs       │
                         │        │                         │                                       │
                         │  LangGraph agents ── MCP client ─┼──▶  MCP server (official SDK)          │
                         │        │                         │      10 controlled tools → services    │
                         │  AI service (provider adapters)  │                                       │
                         └────────┼─────────────────────────┼───────────────────────────────────────┘
                                  │                         │
            Qwen / Llama / OpenAI-compatible (vLLM, hosted)  PostgreSQL 16 + pgvector · Redis · object storage
```

The system is a **modular monolith** with one separately deployable component (the MCP server). Model inference is
external (self-hosted vLLM or hosted APIs) behind adapters. No microservices without a reason.

## Modules (backend/app)

| Package | Responsibility |
|---|---|
| `core/` | config (env), DB session, security primitives & permission catalogue, error envelope, rate limiter, JSON logging |
| `models/` | SQLAlchemy models — UUID PKs, timestamps, `org_id` tenant column, soft delete where appropriate |
| `services/` | deterministic domain logic: application workflow, rules (requirements, risk), assessments & review, tools (MCP capability layer), audit, storage/scanning adapters |
| `rag/` | extraction, normalisation, chunking, indexing, hybrid retrieval, grounded answers, evaluation |
| `ai/` | provider adapters (Qwen, Llama, OpenAI-compatible, mock), AI service (structured output, retries, telemetry, runtime switching), prompt-injection guard |
| `agents/` | LangGraph graph, six agent nodes, runtime (budget, step recorder, MCP tool client) |
| `reports/` | Arabic/English PDF generation with embedded fonts |
| `api/v1/` | thin FastAPI routers |
| `seed/` | synthetic corpus, companies, requirements, evaluation dataset |

## Key decisions (ADR summary)

1. **Deterministic rules for mandatory checks.** Required documents, configured requirement rules and risk-indicator rules
   run as code over configuration tables. Agents add context (evidence retrieval, phrasing, summaries) but never decide
   whether a mandatory check passed. This keeps critical outcomes reproducible and testable.
2. **Agents only touch data through MCP tools.** The same authorisation, validation, rate limiting and audit path applies
   to agents and external clients. Per-agent tool allow-lists provide least privilege inside the workflow. No generic SQL,
   file or network tool exists.
3. **Human checkpoint is structural.** The graph's terminal node submits for review; `decide()` refuses any non-USER
   principal (`HUMAN_REQUIRED`) and consequential decisions require explicit confirmation.
4. **Evidence and interpretation are separate fields** on every finding; citations point to chunk ids and are verified
   against the stored chunk text (`verified` flag). Model-cited ids that were never supplied are dropped.
5. **Provider independence with capability probing.** Structured output strategy is chosen from probed capabilities
   (json_schema → json_object → prompt-only), always followed by Pydantic validation and one repair round.
6. **Honest mock mode.** Without credentials the "LLM" is a deterministic extractive builder; every artefact is flagged
   `is_mock` and the UI shows "وضع المحاكاة". Real adapters remain in place and are unit-tested with mocked HTTP.
7. **Vector store adapter.** pgvector (HNSW, cosine) when available; otherwise a portable `float8[]` column with exact
   NumPy cosine. Keyword search uses Postgres `tsvector` over Arabic-normalised, lightly stemmed tokens.
8. **Version-aware knowledge base.** Uploading an existing document code creates a new version; older versions become
   `SUPERSEDED` and are excluded from retrieval unless requested. Missing metadata (dates, pages) is stored as null and
   shown as "غير مُدخل / بدون ترقيم صفحات" — never fabricated.
9. **Edits are versions.** Analyst edits create a new draft version (`authored_by=MIXED|HUMAN`), preserving the AI original.
10. **Arabic-first frontend.** Direction is set server-side from a cookie (no flash), components use logical properties
    (`ms/me/ps/pe/start/end`), charts reverse their time axis and move value axes to the right in RTL, identifiers are
    isolated with `.ltr` (`unicode-bidi: isolate`).

## Data model

`organizations, users, roles, permissions (+role_permissions, user_roles), mcp_api_keys, system_settings,
fintech_applications, application_documents, application_comments, application_events, regulatory_documents,
regulatory_document_versions, regulatory_chunks (tsvector GIN), embeddings (vector/HNSW), regulatory_requirements,
agent_runs, agent_steps, assessment_drafts, assessment_findings, assessment_citations, analyst_reviews, audit_logs,
model_invocations, request_metrics, ai_models, ai_use_cases, governance_controls, model_evaluations`.

Every tenant-owned table carries `org_id`; services resolve resources through tenant-checked getters that return 404
for other tenants (no existence oracle). Migrations live in `backend/alembic/versions`.

## Application workflow

`DRAFT → SUBMITTED → (DOCUMENT_PROCESSING) → AI_ANALYSIS → PENDING_HUMAN_REVIEW → ADDITIONAL_INFORMATION_REQUIRED | APPROVED_FOR_NEXT_REVIEW_STAGE → CLOSED`

Transitions and the permission required for each are defined in `services/applications.py::TRANSITIONS`. AI-managed
states (`AI_ANALYSIS`, `PENDING_HUMAN_REVIEW`) and `APPROVED_FOR_NEXT_REVIEW_STAGE` cannot be set through the generic
transition endpoint.
