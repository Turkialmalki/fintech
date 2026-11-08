# Deployment & runbooks

## Topology
`web` (Next.js standalone) · `api` (FastAPI, stateless, HPA) · `mcp` (MCP server, stateless) · PostgreSQL 16 + pgvector ·
Redis · S3-compatible object storage · optional vLLM/TEI inference on GPU nodes · optional ClamAV.

## Environments
`infra/k8s/base` + `overlays/staging|production` (kustomize) or `infra/helm/rip` (Helm). Config in a ConfigMap; secrets via
External Secrets from the cloud secret manager (`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `S3_BUCKET`, model API keys).

## AWS reference (Terraform, `infra/terraform/aws`)
```bash
cd infra/terraform/aws
terraform init -backend-config=env/production.backend.hcl
terraform apply -var-file=env/production.tfvars
```
Creates VPC (3 AZ), EKS (+ optional GPU node group), RDS PostgreSQL 16 (encrypted, Multi-AZ in prod, 30-day backups,
`rds.force_ssl`), ElastiCache Redis (TLS), S3 (KMS, versioned, public access blocked), ECR (immutable, scan on push),
KMS and Secrets Manager. Choose a region that satisfies data-residency requirements for your data classification.
**Azure:** AKS, PostgreSQL Flexible Server (pgvector extension allow-listed), Azure Cache for Redis, Blob Storage, Key Vault.
**GCP:** GKE, Cloud SQL for PostgreSQL (pgvector), Memorystore, GCS, Secret Manager. Only `services/storage.py` (S3 adapter)
and the secret wiring are cloud-specific.

## Release (GitHub Actions)
`ci.yml`: backend tests on Postgres+pgvector & Redis, frontend type-check/tests/build, E2E on Docker Compose, Trivy +
pip-audit, signed images with SBOM pushed to GHCR. `deploy.yml`: manual dispatch → `helm upgrade --install` (production
environment requires approval) → rollout status.

## Database migrations
Alembic; the `migrate` Job/hook runs `alembic upgrade head` before pods roll. Use expand → migrate → contract: add
nullable columns / new tables first, deploy code that writes both, backfill, then remove old columns in a later release.
Never edit an applied migration. Rollback = deploy previous image (schema stays backward compatible) — `alembic downgrade`
only for unreleased migrations.

## Backup & recovery
- RDS automated backups + PITR (30 days prod); weekly snapshot copied to a second region; quarterly restore drill:
  restore to a new instance → point a staging `DATABASE_URL` at it → run `pytest -q tests/test_rag.py` smoke + login.
- S3 versioning + noncurrent-version expiry (90 d); optional cross-region replication.
- RPO ≤ 5 min (PITR), RTO ≤ 1 h (restore + redeploy). Redis holds only rate-limit counters (no backup needed).
- Re-indexing: embeddings can be rebuilt from stored originals by re-uploading versions (planned admin command).

## Observability
JSON logs to stdout (request id, route, status, latency); `/metrics` (Prometheus); OpenTelemetry traces when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set and the OTel SDK is installed; in-app monitoring at **سجل العمليات → المراقبة والأداء**
(API p50/p95, errors, model latency/tokens/cost, agent duration, tool failures, retrieval latency, citation accuracy,
human correction rate). Alert on: 5xx rate > 1%, p95 > 1.5 s, agent failure rate > 10%, citation accuracy < 90%.

## Health
`/healthz` (liveness), `/readyz` (DB required, Redis degraded allowed), MCP `/healthz`, web `/login`.

## GPU inference capacity
`overlays/production/inference-gpu.yaml` runs Qwen2.5-72B-AWQ on 2 GPUs with vLLM (≈32k context). Rough sizing: one
replica serves ~10–20 concurrent assessment calls; each assessment makes 3–4 model calls. Scale replicas with queue depth /
`vllm:num_requests_waiting`; keep embeddings (BGE-M3 on TEI) on a small separate GPU or CPU pool. Smaller footprint:
Qwen2.5-32B or Llama-3.1-8B on a single GPU.

## Runbook snippets
| Symptom | Action |
|---|---|
| Runs stuck `RUNNING` after a pod restart | In-process runs die with the pod; mark as failed (`UPDATE agent_runs SET status='FAILED' WHERE status='RUNNING' AND started_at < now()-interval '15 min'`) and re-run. Production: move runs to a worker queue. |
| `PROVIDER_NOT_CONFIGURED` when switching model | Set `<PROVIDER>_BASE_URL` (and key) in the secret/config, restart api. |
| Probe shows `tool_calling: false` on vLLM | Start vLLM with `--enable-auto-tool-choice --tool-call-parser …`. |
| Readiness failing | Check DB connectivity/SSL; Redis outage alone does not fail readiness. |
| Embedding dim error | `EMBEDDING_DIM` mismatches the model/column — see AI_MODELS.md. |
