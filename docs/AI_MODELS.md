# AI models, evaluation and mock mode

## Provider layer
`app/ai/providers/` contains `QwenProvider`, `LlamaProvider` and `OpenAICompatibleProvider` (all speak `/v1/chat/completions`
and `/v1/embeddings`) plus `MockLLMProvider` and `HashingEmbeddings`. `app/ai/service.py::AIService` adds retries with
backoff (retryable: timeouts, 429, 5xx), structured output, streaming and telemetry (`model_invocations`: latency,
tokens, cost, success, mock flag). Business code only calls `AIService`.

| Variable | Meaning |
|---|---|
| `AI_PROVIDER` | `mock` \| `qwen` \| `llama` \| `openai_compatible` |
| `AI_MODEL`, `AI_BASE_URL`, `AI_API_KEY` | defaults for the env-selected provider |
| `QWEN_BASE_URL`/`QWEN_API_KEY`, `LLAMA_BASE_URL`/`LLAMA_API_KEY`, `OPENAI_COMPATIBLE_BASE_URL`/`…_API_KEY` | per-provider endpoints enabling runtime switching |
| `AI_TEMPERATURE`, `AI_MAX_TOKENS`, `AI_TIMEOUT_SECONDS` | generation settings |
| `AI_COST_PER_1K_INPUT`, `AI_COST_PER_1K_OUTPUT` | for cost reporting (USD) |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_DIM` | independent embedding config |

### Qwen
- Self-hosted: `vllm serve Qwen/Qwen2.5-72B-Instruct --enable-auto-tool-choice --tool-call-parser hermes` (or an AWQ/GPTQ
  variant on fewer GPUs). Set `QWEN_BASE_URL=http://<host>:8000/v1`.
- Hosted: Alibaba Cloud Model Studio OpenAI-compatible endpoint, e.g. `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
  with `QWEN_API_KEY` and a model such as `qwen-plus`. Check the region/endpoint that meets your data-residency needs.

### Llama
- Self-hosted: `vllm serve meta-llama/Llama-3.3-70B-Instruct --enable-auto-tool-choice --tool-call-parser llama3_json`.
  Set `LLAMA_BASE_URL`. Accept the Llama licence on Hugging Face first.
- Any OpenAI-compatible host serving Llama works the same way.

### Switching and probing
Admins choose provider + model in **Settings → Model configuration** (stored in `system_settings` as `ai.active_provider`,
no secrets). **Probe capabilities** sends tiny requests to detect chat, `json_schema`, `json_object`, tool calling and
streaming; results are stored on the matching governance model record. The structured-output strategy follows the probe:
json_schema → json_object → schema-in-prompt, then Pydantic validation and one repair attempt. Never assumed.

### Embeddings
Changing `EMBEDDING_DIM` requires a matching vector column: set the env var before running the first migration (or add a
migration that alters `embeddings.vector` and re-index by re-uploading documents). Recommended multilingual models for
Arabic/English: BGE-M3 (1024-d) or multilingual-e5-large (1024-d), served by TEI or vLLM.

## Mock mode (current demo state)
No credentials were available while building, so the demo runs with `AI_PROVIDER=mock` and `EMBEDDING_PROVIDER=mock`:
- The "LLM" returns deterministic, extractive output assembled from retrieved evidence and rule results (callers pass a
  `mock_builder`). It does not reason, and its text is prefixed "[وضع المحاكاة] / [Mock]".
- Embeddings are lexical feature hashing over normalised, lightly stemmed tokens — semantically weak but sufficient to
  exercise the full vector pipeline.
- Every run, invocation, evaluation and draft is flagged `is_mock`; the header shows "وضع المحاكاة".
- **Qwen and Llama integrations are implemented and tested against mocked HTTP servers, but have not been exercised
  against a live model in this environment.** Configure an endpoint and use *Probe capabilities* to verify.

## Evaluation
`app/seed/data/rag_eval.json` (14 Arabic/English questions with gold document+section). Run from **AI governance → Run
RAG evaluation** or `POST /api/v1/governance/evaluations/run`. Metrics: precision@k, recall@k, MRR, context relevance,
groundedness, answer relevance, citation correctness, per-language breakdown, latency. Results are stored in
`model_evaluations` and shown in the governance and observability views.

Latest mock-mode run (k=5): recall@5 = 1.00, MRR = 0.96, groundedness = 1.00, citation correctness ≈ 0.85,
precision@5 = 0.20 (the ceiling is 0.20 because each question has one gold section). These numbers measure the
retrieval/citation pipeline, not a language model. Re-run after configuring a real model to compare Arabic vs English
accuracy, tool-call reliability, latency, tokens and cost. A confidence score reported by a model is never treated as accuracy.
