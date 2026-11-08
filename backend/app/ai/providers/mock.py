"""Clearly-labelled MOCK providers for running without model credentials.

The mock LLM never pretends to reason: callers pass a deterministic `mock_builder` that
assembles the output from retrieved evidence and rules, and every result is flagged
`is_mock=True` so the UI shows "وضع المحاكاة / Mock mode".
"""
from __future__ import annotations

import hashlib
import json
import math

from app.ai.providers.base import Capabilities, EmbeddingProvider, LLMProvider, LLMResult
from app.rag.normalize import normalize, tokenize


class MockLLMProvider(LLMProvider):
    name = "mock"
    is_mock = True

    def __init__(self, model: str = "deterministic-mock-v1"):
        super().__init__(model or "deterministic-mock-v1")
        self.capabilities = Capabilities(chat=True, streaming=True, json_mode=True, json_schema=True,
                                         tool_calling=False, probed=True,
                                         notes=["Deterministic mock: no language model is called."])
        self.next_payload: dict | str | None = None

    def chat(self, messages, *, temperature=0.1, max_tokens=1024, response_format=None, tools=None) -> LLMResult:
        payload = self.next_payload
        self.next_payload = None
        if payload is None:
            last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            text = "[MOCK] " + str(last)[:200]
        else:
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        prompt_len = sum(len(str(m.get("content", ""))) for m in messages)
        return LLMResult(text=text, provider=self.name, model=self.model, tokens_in=prompt_len // 3,
                         tokens_out=len(text) // 3, latency_ms=1, is_mock=True)


class HashingEmbeddings(EmbeddingProvider):
    """Feature-hashing embedder over stemmed tokens, token bigrams and character trigrams.

    Lexical, not semantic: good enough to exercise the full vector pipeline offline and
    explicitly labelled as a mock in the UI and evaluation records.
    """

    name = "mock"
    is_mock = True

    def __init__(self, dim: int = 384):
        super().__init__("hashing-ngram-v1", dim)

    def _features(self, text: str) -> list[tuple[str, float]]:
        toks = tokenize(text)
        feats: list[tuple[str, float]] = [(f"w:{t}", 1.0) for t in toks]
        feats += [(f"b:{a}_{b}", 0.6) for a, b in zip(toks, toks[1:])]
        for t in toks:
            padded = f"#{t}#"
            feats += [(f"c:{padded[i:i + 3]}", 0.25) for i in range(len(padded) - 2)]
        return feats

    def embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feat, w in self._features(normalize(text)):
            h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign * w
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]
