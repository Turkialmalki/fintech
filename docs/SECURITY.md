# Security model

| Control | Where |
|---|---|
| Authentication | JWT HS256 access (60 min) + refresh (7 d) tokens with `typ` claim; refresh tokens cannot be used as access tokens. Constant-work password check (bcrypt, cost 12) to avoid user enumeration. Login rate limit per IP+email. |
| Authorisation | `core/security.py` permission catalogue and roles; `api/deps.require()` on every route; denials audited. Deterministic — model output is never consulted. |
| Tenant isolation | `org_id` on all tenant data; token `org` claim must match the user's current org; tenant-checked getters return 404 across tenants; retrieval, MCP tools and dashboards filter by org. Covered by tests. |
| Least privilege | 5 roles; MCP keys read-only by default; write tools need an explicit `write` scope; per-agent tool allow-lists. |
| Human approval | Review decisions only by `actor_type=USER`; consequential decisions need `confirmed=true` and the right permission; UI requires an acknowledgement checkbox. |
| File handling | Extension allow-list, magic-byte sniffing (PDF header, DOCX zip structure + zip-bomb guard, UTF-8 text), size limit, encrypted PDFs rejected, optional ClamAV INSTREAM scan, storage keys are random (no user-controlled paths), path traversal guard. |
| Prompt injection | Retrieved and uploaded text is wrapped in `<untrusted_document>` delimiters with look-alike tags neutralised; system policy forbids following embedded instructions; Arabic+English pattern scan flags injections, which become a HIGH risk finding; citation ids are validated; no model output drives authorisation or state changes. |
| Rate limiting | Redis fixed-window per token/IP on the API, per principal on MCP tools; in-process fallback if Redis is down (logged). |
| Audit | Append-only `audit_logs` for auth, application, document, retrieval, model, agent, MCP, review, governance and settings events; denial/failure events written in an isolated transaction so they survive rollbacks; redaction of secrets, e-mails, IBANs and national IDs. |
| Secrets | Env / secret manager only (External Secrets in K8s). Model keys are never stored in the DB; `/ai/config` reports only whether a key is configured. |
| Transport | HSTS, nosniff, frame-deny, no-referrer headers; TLS terminated at ingress; DB `sslmode=require` and Redis TLS in the Terraform reference. |
| Data retention | `DATA_RETENTION_DAYS` setting; S3 noncurrent-version lifecycle in Terraform. |

## Tests
`tests/test_auth_rbac_tenancy.py`, `tests/test_ai_security.py` (injection patterns, delimiter neutralisation, redaction,
SQL-injection inertness, rate limiting), `tests/test_mcp_agents.py` (MCP auth, read-only default, agents cannot decide,
budget enforcement), `tests/test_applications_reviews.py` (file validation, workflow guards, confirmation).

## Known limitations (be explicit)
- Browser tokens live in `sessionStorage`; a production deployment should move to an httpOnly-cookie BFF with CSRF protection.
- No MFA/SSO yet (designed to sit behind an OIDC provider; add `fastapi` OIDC dependency in `api/deps.py`).
- Malware scanning is off unless `FILE_SCANNER=clamav` and a ClamAV service are configured; uploads record `NOT_SCANNED` honestly.
- Prompt-injection detection is pattern-based and defence-in-depth, not a guarantee; the structural controls (no model-driven authorisation, human checkpoint, tool scopes) are the real safeguards.
- Agent runs execute in an in-process background thread for demo simplicity; production should use a worker queue (the run model and status polling already support this).
- Framework mappings in AI governance are configurable review aids, not evidence of legal or regulatory compliance.
