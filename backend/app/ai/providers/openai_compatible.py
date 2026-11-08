"""OpenAI-compatible Chat Completions / Embeddings adapter.

Works with vLLM, TGI (OpenAI mode), Ollama, LM Studio, DashScope compatible-mode,
Together, Fireworks, Groq and any other server that implements /v1/chat/completions.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.ai.providers.base import Capabilities, EmbeddingProvider, LLMProvider, LLMResult, ProviderError


def _approx_tokens(text: str) -> int:
    # Rough estimate used only when a server omits usage. Arabic tokenises denser than English.
    return max(1, len(text) // 3)


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, model: str, base_url: str, api_key: str = "", timeout: float = 60.0,
                 extra_headers: dict | None = None, transport: httpx.BaseTransport | None = None):
        super().__init__(model)
        if not base_url:
            raise ProviderError(f"{self.name}: AI_BASE_URL is not configured")
        if not model:
            raise ProviderError(f"{self.name}: AI_MODEL is not configured")
        self.base_url = base_url.rstrip("/")
        headers = {"Content-Type": "application/json", **(extra_headers or {})}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout, transport=transport)

    # -- request helpers -----------------------------------------------------------------
    def _payload(self, messages, temperature, max_tokens, response_format=None, tools=None, stream=False) -> dict:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature,
                                "max_tokens": max_tokens, "stream": stream}
        if response_format is not None:
            body["response_format"] = self._adapt_response_format(response_format)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        return body

    def _adapt_response_format(self, response_format: dict) -> dict:
        """Hook for providers that spell structured output differently."""
        return response_format

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self._client.post(path, json=body)
        except httpx.TimeoutException as e:
            raise ProviderError(f"{self.name} timeout: {e}", retryable=True) from e
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} connection error: {e}", retryable=True) from e
        if r.status_code >= 500 or r.status_code == 429:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}", retryable=True)
        if r.status_code >= 400:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    # -- API -------------------------------------------------------------------------------
    def chat(self, messages, *, temperature=0.1, max_tokens=1024, response_format=None, tools=None) -> LLMResult:
        t0 = time.perf_counter()
        data = self._post("/chat/completions", self._payload(messages, temperature, max_tokens, response_format, tools))
        latency = int((time.perf_counter() - t0) * 1000)
        try:
            choice = data["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"{self.name}: malformed response") from e
        text = choice.get("content") or ""
        usage = data.get("usage") or {}
        tool_calls = []
        for tc in choice.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_raw": fn.get("arguments")}
            tool_calls.append({"id": tc.get("id"), "name": fn.get("name"), "arguments": args})
        prompt_text = " ".join(str(m.get("content", "")) for m in messages)
        return LLMResult(
            text=text, provider=self.name, model=data.get("model", self.model),
            tokens_in=int(usage.get("prompt_tokens") or _approx_tokens(prompt_text)),
            tokens_out=int(usage.get("completion_tokens") or _approx_tokens(text)),
            latency_ms=latency, tool_calls=tool_calls, raw={"id": data.get("id")},
        )

    def stream(self, messages, *, temperature=0.1, max_tokens=1024) -> Iterator[str]:
        body = self._payload(messages, temperature, max_tokens, stream=True)
        try:
            with self._client.stream("POST", "/chat/completions", json=body) as r:
                if r.status_code >= 400:
                    raise ProviderError(f"{self.name} HTTP {r.status_code}")
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0].get("delta", {}).get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} stream error: {e}", retryable=True) from e

    def probe(self) -> Capabilities:
        """Test capabilities with tiny live requests before enabling them."""
        caps = Capabilities(probed=True)
        ping = [{"role": "user", "content": "Reply with the single word: ok"}]
        try:
            self.chat(ping, max_tokens=5)
            caps.chat = True
        except ProviderError as e:
            caps.chat = False
            caps.notes.append(f"chat failed: {e}")
            self.capabilities = caps
            return caps
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
        try:
            r = self.chat([{"role": "user", "content": 'Return JSON {"ok": true}'}], max_tokens=20,
                          response_format={"type": "json_schema", "json_schema": {"name": "probe", "schema": schema}})
            json.loads(r.text)
            caps.json_schema = True
            caps.json_mode = True
        except (ProviderError, json.JSONDecodeError) as e:
            caps.notes.append(f"json_schema unsupported: {str(e)[:120]}")
            try:
                r = self.chat([{"role": "user", "content": 'Return JSON {"ok": true}'}], max_tokens=20,
                              response_format={"type": "json_object"})
                json.loads(r.text)
                caps.json_mode = True
            except (ProviderError, json.JSONDecodeError) as e2:
                caps.notes.append(f"json_object unsupported: {str(e2)[:120]}")
        tool = {"type": "function", "function": {"name": "get_time", "description": "Get the time",
                                                 "parameters": {"type": "object", "properties": {}}}}
        try:
            r = self.chat([{"role": "user", "content": "Call the get_time tool."}], max_tokens=50, tools=[tool])
            caps.tool_calling = bool(r.tool_calls)
            if not r.tool_calls:
                caps.notes.append("model did not emit a tool call")
        except ProviderError as e:
            caps.notes.append(f"tool calling unsupported: {str(e)[:120]}")
        try:
            caps.streaming = any(True for _ in self.stream(ping, max_tokens=5))
        except ProviderError as e:
            caps.notes.append(f"streaming unsupported: {str(e)[:120]}")
        self.capabilities = caps
        return caps


class QwenProvider(OpenAICompatibleProvider):
    """Qwen via DashScope compatible-mode or a self-hosted vLLM serving Qwen weights.

    DashScope accepts `json_object` but not every deployment accepts `json_schema`; probing decides.
    """

    name = "qwen"


class LlamaProvider(OpenAICompatibleProvider):
    """Meta Llama via vLLM / TGI / Ollama / hosted OpenAI-compatible APIs.

    Tool calling on vLLM requires `--enable-auto-tool-choice --tool-call-parser llama3_json`;
    probing detects whether it is enabled.
    """

    name = "llama"


class OpenAICompatibleEmbeddings(EmbeddingProvider):
    name = "openai_compatible"

    def __init__(self, model: str, dim: int, base_url: str, api_key: str = "", timeout: float = 60.0,
                 transport: httpx.BaseTransport | None = None):
        super().__init__(model, dim)
        if not base_url or not model:
            raise ProviderError("EMBEDDING_BASE_URL and EMBEDDING_MODEL must be configured")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 32):
            try:
                r = self._client.post("/embeddings", json={"model": self.model, "input": texts[i:i + 32]})
            except httpx.HTTPError as e:
                raise ProviderError(f"embedding error: {e}", retryable=True) from e
            if r.status_code >= 400:
                raise ProviderError(f"embedding HTTP {r.status_code}: {r.text[:200]}", retryable=r.status_code >= 500)
            vecs = [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
            for v in vecs:
                if len(v) != self.dim:
                    raise ProviderError(f"embedding dim {len(v)} != EMBEDDING_DIM {self.dim}")
            out.extend(vecs)
        return out
