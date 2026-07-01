"""OpenAI implementation of LLMProvider.

Uses the `openai` SDK against the default OpenAI endpoint. Needs OPENAI_API_KEY.

(Near-identical to deepseek_provider / ollama_provider — all OpenAI-compatible. Once you have a
moment, factoring a shared `_OpenAICompatProvider` base is the obvious cleanup; kept separate here
so each reads on its own.)
"""

from __future__ import annotations

import json
from typing import Any

from langsmith.wrappers import wrap_openai
from openai import OpenAI

from nexus_refactor.config import get_settings
from nexus_refactor.llm.base import LLMResult


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        s = get_settings()
        self.model = model or s.openai_model
        # Built here (not at import) so importing this module never needs a key.
        # wrap_openai → LLM calls become LangSmith spans when tracing is on (no-op otherwise).
        self._client = wrap_openai(OpenAI(api_key=s.openai_api_key or None))

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
        # OpenAI also supports strict `json_schema` structured outputs; JSON mode + the schema in
        # the prompt is the portable choice that matches the other providers.
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
