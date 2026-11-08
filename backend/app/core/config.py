"""Application configuration. All values come from environment variables (12-factor).

Secrets (JWT secret, model API keys) are read from the environment or a mounted secret
store and are never persisted to ordinary database records.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- runtime ---
    environment: Literal["local", "test", "staging", "production"] = "local"
    app_name: str = "Saudi Fintech Regulatory Intelligence Platform"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    demo_mode: bool = True  # enables synthetic data banner & seed endpoint
    # Serverless (e.g. Vercel): no connection pooling in-process, no background threads, self-bootstrap.
    serverless: bool = Field(default_factory=lambda: bool(__import__("os").getenv("VERCEL")))
    auto_bootstrap: bool = False  # run migrations + demo seed on first request if the database is empty

    # --- database / cache ---
    database_url: str = "postgresql+psycopg://rip:rip@localhost:5432/rip"
    redis_url: str = "redis://localhost:6379/0"
    # "auto" uses pgvector when the extension is installed, otherwise a portable float8[] column.
    vector_backend: Literal["auto", "pgvector", "array"] = "auto"

    # --- security ---
    jwt_secret: SecretStr = SecretStr("change-me-local-only-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 7
    rate_limit_per_minute: int = 240
    login_rate_limit_per_minute: int = 10
    max_upload_mb: int = 20
    file_scanner: Literal["none", "clamav"] = "none"
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    storage_dir: str = "./storage"
    data_retention_days: int = 365

    # --- AI ---
    ai_provider: Literal["mock", "qwen", "llama", "openai_compatible"] = "mock"
    ai_model: str = ""
    ai_base_url: str = ""
    ai_api_key: SecretStr = SecretStr("")
    ai_temperature: float = 0.1
    ai_max_tokens: int = 1500
    ai_timeout_seconds: float = 60.0
    ai_cost_per_1k_input: float = 0.0
    ai_cost_per_1k_output: float = 0.0

    embedding_provider: Literal["mock", "openai_compatible"] = "mock"
    embedding_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_dim: int = 384

    # --- agents ---
    agent_max_steps: int = 24
    agent_timeout_seconds: float = 300.0
    agent_max_tool_calls: int = 40
    agent_token_budget: int = 60000
    agent_retry_attempts: int = 2
    agent_tool_transport: Literal["mcp_inprocess", "mcp_http"] = "mcp_inprocess"
    agent_run_mode: Literal["thread", "sync"] = "thread"  # "sync" for serverless platforms
    mcp_url: str = "http://localhost:8765/mcp"

    # --- MCP server ---
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8765
    mcp_rate_limit_per_minute: int = 120

    rag_top_k: int = 6
    rag_min_score: float = 0.18

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def _from_platform_env(s: Settings) -> Settings:
    """Adopt credentials injected by platform integrations, so secrets never have to be copied by hand.

    - Supabase ↔ Vercel integration injects POSTGRES_URL (pooler). We switch it to session mode (port 5432),
      the psycopg driver, and the dedicated `rip` schema (not exposed by Supabase's REST API).
    - If JWT_SECRET is not set, derive an application-specific key from SUPABASE_JWT_SECRET (HMAC, never reused directly).
    """
    import hashlib
    import hmac
    import os
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    if not os.getenv("DATABASE_URL") and os.getenv("POSTGRES_URL"):
        u = urlsplit(os.environ["POSTGRES_URL"])
        host = u.hostname or ""
        port = 5432 if "pooler.supabase.com" in host else (u.port or 5432)
        netloc = u.netloc.rsplit("@", 1)[0] + f"@{host}:{port}"
        q = {k: v for k, v in parse_qsl(u.query) if k in ("sslmode",)}
        q.setdefault("sslmode", "require")
        q["options"] = "-csearch_path=rip,extensions"
        s.database_url = urlunsplit(("postgresql+psycopg", netloc, u.path or "/postgres", urlencode(q), ""))
    default_secret = "change-me-local-only-secret-change-me"
    if s.jwt_secret.get_secret_value() == default_secret and os.getenv("SUPABASE_JWT_SECRET"):
        derived = hmac.new(os.environ["SUPABASE_JWT_SECRET"].encode(), b"rip-api-jwt-v1", hashlib.sha256).hexdigest()
        s.jwt_secret = SecretStr(derived)
    if s.environment == "production" and s.jwt_secret.get_secret_value() == default_secret:
        raise RuntimeError("JWT_SECRET must be set in production")
    return s


@lru_cache
def get_settings() -> Settings:
    return _from_platform_env(Settings())


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings", "Field"]
