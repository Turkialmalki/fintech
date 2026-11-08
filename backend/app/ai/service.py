"""Provider-independent AI service: factory, runtime switching, structured output, telemetry.

Business logic depends only on `AIService`; the concrete provider is chosen from
configuration (env defaults, optionally overridden at runtime by an admin through the
`ai.active_provider` system setting). Secrets are always read from the environment.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.providers.base import EmbeddingProvider, LLMProvider, LLMResult, ProviderError
from app.ai.providers.mock import HashingEmbeddings, MockLLMProvider
from app.ai.providers.openai_compatible import (
    LlamaProvider,
    OpenAICompatibleEmbeddings,
    OpenAICompatibleProvider,
    QwenProvider,
)
from app.core.config import settings

log = logging.getLogger("rip.ai")
T = TypeVar("T", bound=BaseModel)

# Telemetry context (set by API/agents so invocations are attributed correctly)
current_org: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("current_org", default=None)
current_run: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("current_run", default=None)

PROVIDER_CLASSES: dict[str, type[OpenAICompatibleProvider]] = {
    "qwen": QwenProvider,
    "llama": LlamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
}

DEFAULT_MODELS = {
    "qwen": "Qwen/Qwen2.5-72B-Instruct",
    "llama": "meta-llama/Llama-3.3-70B-Instruct",
    "openai_compatible": "",
    "mock": "deterministic-mock-v1",
}


@dataclass
class ProviderConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    source: str  # env | runtime

    def public(self) -> dict:
        return {"provider": self.provider, "model": self.model, "base_url": self.base_url,
                "api_key_configured": bool(self.api_key), "source": self.source}


def _env(name: str) -> str:
    return os.getenv(name, "")


def resolve_config(override: dict | None = None) -> ProviderConfig:
    provider = (override or {}).get("provider") or settings.ai_provider
    model = (override or {}).get("model") or (settings.ai_model if provider == settings.ai_provider else "") \
        or DEFAULT_MODELS.get(provider, "")
    prefix = provider.upper()
    base_url = _env(f"{prefix}_BASE_URL") or (settings.ai_base_url if provider == settings.ai_provider else "")
    api_key = _env(f"{prefix}_API_KEY") or (settings.ai_api_key.get_secret_value() if provider == settings.ai_provider else "")
    return ProviderConfig(provider, model, base_url, api_key, "runtime" if override else "env")


def build_llm(cfg: ProviderConfig) -> LLMProvider:
    if cfg.provider == "mock":
        return MockLLMProvider(cfg.model)
    cls = PROVIDER_CLASSES.get(cfg.provider)
    if cls is None:
        raise ProviderError(f"unknown provider {cfg.provider}")
    return cls(cfg.model, cfg.base_url, cfg.api_key, timeout=settings.ai_timeout_seconds)


def build_embedder() -> EmbeddingProvider:
    if settings.embedding_provider == "mock":
        return HashingEmbeddings(settings.embedding_dim)
    return OpenAICompatibleEmbeddings(
        settings.embedding_model, settings.embedding_dim, settings.embedding_base_url,
        settings.embedding_api_key.get_secret_value(), timeout=settings.ai_timeout_seconds,
    )


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if not m:
            raise
        return json.loads(m.group(0))


class AIService:
    def __init__(self, llm: LLMProvider, embedder: EmbeddingProvider, cfg: ProviderConfig):
        self.llm = llm
        self.embedder = embedder
        self.cfg = cfg

    @property
    def is_mock(self) -> bool:
        return self.llm.is_mock

    # ---- telemetry -------------------------------------------------------------------
    def _record(self, operation: str, purpose: str, result: LLMResult | None, latency_ms: int, ok: bool, err: str = "",
                model: str | None = None, provider: str | None = None, is_mock: bool | None = None) -> None:
        from app.core.db import session_scope
        from app.models import ModelInvocation

        tin = result.tokens_in if result else 0
        tout = result.tokens_out if result else 0
        cost = tin / 1000 * settings.ai_cost_per_1k_input + tout / 1000 * settings.ai_cost_per_1k_output
        try:
            with session_scope() as db:
                db.add(ModelInvocation(
                    org_id=current_org.get(), provider=provider or self.llm.name, model=model or self.llm.model,
                    operation=operation, purpose=purpose, agent_run_id=current_run.get(), latency_ms=latency_ms,
                    tokens_in=tin, tokens_out=tout, cost_usd=round(cost, 6), success=ok,
                    is_mock=self.llm.is_mock if is_mock is None else is_mock, error=err[:500],
                ))
        except Exception:
            log.exception("failed to record model invocation")

    # ---- generation ------------------------------------------------------------------
    def chat(self, messages: list[dict], *, purpose: str, max_tokens: int | None = None,
             mock_text: str | None = None, tools: list[dict] | None = None) -> LLMResult:
        if self.is_mock and mock_text is not None:
            self.llm.next_payload = mock_text  # type: ignore[attr-defined]
        return self._call(messages, purpose=purpose, max_tokens=max_tokens, tools=tools)

    def _call(self, messages, *, purpose, max_tokens=None, response_format=None, tools=None) -> LLMResult:
        attempts = settings.agent_retry_attempts + 1
        last: Exception | None = None
        for attempt in range(attempts):
            t0 = time.perf_counter()
            try:
                res = self.llm.chat(messages, temperature=settings.ai_temperature,
                                    max_tokens=max_tokens or settings.ai_max_tokens,
                                    response_format=response_format, tools=tools)
                self._record("chat" if response_format is None else "json", purpose, res,
                             int((time.perf_counter() - t0) * 1000), True)
                return res
            except ProviderError as e:
                last = e
                self._record("chat", purpose, None, int((time.perf_counter() - t0) * 1000), False, str(e))
                if not e.retryable or attempt == attempts - 1:
                    raise
                time.sleep(min(2 ** attempt * 0.5, 4))
        raise last  # pragma: no cover

    def structured(self, messages: list[dict], schema: type[T], *, purpose: str,
                   mock_builder: Callable[[], dict] | None = None, max_tokens: int | None = None) -> tuple[T, LLMResult]:
        """Return a validated Pydantic object.

        Strategy depends on probed capabilities: json_schema → json_object → prompt-only,
        always followed by Pydantic validation and one repair retry.
        """
        if self.is_mock:
            if mock_builder is None:
                raise ProviderError("mock mode requires a deterministic mock_builder")
            self.llm.next_payload = mock_builder()  # type: ignore[attr-defined]
            res = self._call(messages, purpose=purpose, max_tokens=max_tokens)
            return schema.model_validate(extract_json(res.text)), res

        caps = self.llm.capabilities
        js = schema.model_json_schema()
        response_format = None
        msgs = list(messages)
        if caps.json_schema:
            response_format = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": js, "strict": False}}
        elif caps.json_mode:
            response_format = {"type": "json_object"}
        msgs = msgs + [{"role": "system", "content": "Respond with a single JSON object that validates against this JSON Schema. "
                                                       "No prose outside JSON.\n" + json.dumps(js, ensure_ascii=False)}]
        res = self._call(msgs, purpose=purpose, max_tokens=max_tokens, response_format=response_format)
        try:
            return schema.model_validate(extract_json(res.text)), res
        except (json.JSONDecodeError, ValidationError) as e:
            repair = msgs + [{"role": "assistant", "content": res.text},
                             {"role": "user", "content": f"The JSON was invalid: {str(e)[:500]}. Return corrected JSON only."}]
            res2 = self._call(repair, purpose=purpose + ":repair", max_tokens=max_tokens, response_format=response_format)
            return schema.model_validate(extract_json(res2.text)), res2

    # ---- embeddings ------------------------------------------------------------------
    def embed(self, texts: list[str], *, purpose: str = "embed") -> list[list[float]]:
        t0 = time.perf_counter()
        try:
            vecs = self.embedder.embed(texts)
        except ProviderError as e:
            self._record("embed", purpose, None, int((time.perf_counter() - t0) * 1000), False, str(e),
                         model=self.embedder.model, provider=self.embedder.name, is_mock=self.embedder.is_mock)
            raise
        fake = LLMResult(text="", provider=self.embedder.name, model=self.embedder.model,
                         tokens_in=sum(len(t) for t in texts) // 3)
        self._record("embed", purpose, fake, int((time.perf_counter() - t0) * 1000), True,
                     model=self.embedder.model, provider=self.embedder.name, is_mock=self.embedder.is_mock)
        return vecs


_cache: dict[str, AIService] = {}


def runtime_override() -> dict | None:
    """Admin-selected provider/model stored in system_settings (no secrets)."""
    from sqlalchemy import select

    from app.core.db import session_scope
    from app.models import SystemSetting

    try:
        with session_scope() as db:
            row = db.scalar(select(SystemSetting).where(SystemSetting.key == "ai.active_provider", SystemSetting.org_id.is_(None)))
            return dict(row.value) if row and row.value else None
    except Exception:
        log.exception("failed to read runtime AI override")
        return None


def get_ai(override: dict | None = None) -> AIService:
    cfg = resolve_config(override if override is not None else runtime_override())
    key = f"{cfg.provider}|{cfg.model}|{cfg.base_url}|{settings.embedding_provider}|{settings.embedding_model}"
    if key not in _cache:
        _cache[key] = AIService(build_llm(cfg), build_embedder(), cfg)
    return _cache[key]


def reset_ai_cache() -> None:
    _cache.clear()
