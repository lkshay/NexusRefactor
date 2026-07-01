"""Ollama (local) implementation of LLMProvider.

Ollama serves an OpenAI-compatible endpoint, so we reuse the `openai` SDK pointed at the local
server. No API key needed (Ollama ignores it; the SDK just wants a non-empty placeholder). Free
and offline — ideal for iterating on the graph without a funded cloud provider.

Prereqs: `ollama serve` running and the model pulled (e.g. `ollama pull qwen3-coder:30b`).

(Near-identical to deepseek_provider — both are OpenAI-compatible. Worth factoring a shared base
once a third one lands; kept separate for now so each is readable on its own.)
"""

from __future__ import annotations

import json
from typing import Any

from langsmith.wrappers import wrap_openai
from openai import OpenAI

from nexus_refactor.config import get_settings
from nexus_refactor.llm.base import LLMResult


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str | None = None) -> None:
        s = get_settings()
        self.model = model or s.ollama_model
        # wrap_openai → LLM calls become LangSmith spans when tracing is on (no-op otherwise).
        self._client = wrap_openai(OpenAI(api_key="ollama", base_url=s.ollama_base_url))

    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> LLMResult:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        usage = resp.usage
        return LLMResult(
            text=resp.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=resp.model,
        )

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, max_tokens: int = 4096
    ) -> dict[str, Any]:
        system_with_schema = (
            f"{system}\n\nReturn a single JSON object matching this JSON Schema:\n"
            f"{json.dumps(schema)}"
        )
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        data: Any = json.loads(resp.choices[0].message.content or "{}")
        return data if isinstance(data, dict) else {}
