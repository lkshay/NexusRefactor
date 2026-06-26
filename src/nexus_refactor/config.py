"""Typed configuration loaded from environment / .env (pydantic-settings).

This file is intentionally complete — it's plumbing, not a learning exercise. Use
`get_settings()` everywhere instead of reading os.environ directly.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM providers (both wired; the router picks per-task) ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "deepseek"  # default route until router.py exists
    anthropic_model: str = ""
    openai_model: str = "gpt-4o"
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    ollama_base_url: str = "http://localhost:11434/v1"  # OpenAI-compatible local endpoint
    ollama_model: str = "qwen3-coder:30b"  # local, code-specialized; override via OLLAMA_MODEL
    
    # --- Observability (LangSmith reads these from the *process env*, see setup_tracing) ---
    langsmith_tracing: bool = True
    langsmith_api_key: str = os.environ.get("LANGSMITH_API_KEY", "")
    langsmith_project: str = "nexus-refactor"

    # --- Retrieval (Qdrant + local fastembed) ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    dense_embed_model: str = "BAAI/bge-small-en-v1.5"
    sparse_embed_model: str = "Qdrant/bm25"

    # --- Agent termination gate (Phase 1a) ---
    max_iterations: int = 4
    token_budget: int = 200_000


@lru_cache
def get_settings() -> Settings:
    """Cached singleton. Safe to call from anywhere."""
    return Settings()


def setup_tracing(settings: Settings) -> None:
    """LangSmith auto-instruments LangGraph when these env vars are present.

    pydantic-settings reads .env into the Settings object but does NOT export to
    os.environ, so LangChain/LangSmith won't see them unless we push them here.
    """
    if not settings.langsmith_tracing:
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
