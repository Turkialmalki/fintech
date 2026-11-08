from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Capabilities:
    """What a provider/model actually supports. Populated by probing, never assumed."""

    chat: bool = True
    streaming: bool = False
    json_mode: bool = False
    json_schema: bool = False
    tool_calling: bool = False
    multimodal: bool = False
    context_window: int | None = None
    probed: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    is_mock: bool = False
    tool_calls: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class ProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class LLMProvider(ABC):
    name: str = "base"
    is_mock: bool = False

    def __init__(self, model: str):
        self.model = model
        self.capabilities = Capabilities()

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        response_format: dict | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResult: ...

    def stream(self, messages: list[dict[str, Any]], *, temperature: float = 0.1, max_tokens: int = 1024) -> Iterator[str]:
        yield self.chat(messages, temperature=temperature, max_tokens=max_tokens).text

    def probe(self) -> Capabilities:
        return self.capabilities


class EmbeddingProvider(ABC):
    name: str = "base"
    is_mock: bool = False

    def __init__(self, model: str, dim: int):
        self.model = model
        self.dim = dim

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...
