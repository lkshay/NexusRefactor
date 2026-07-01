"""DeepSeek implementation of LLMProvider.

DeepSeek's API is OpenAI-compatible, so we drive it with the `openai` SDK pointed at DeepSeek's
base URL. Needs DEEPSEEK_API_KEY (see .env / config).

Models (verified via the /models endpoint): `deepseek-v4-flash` or `deepseek-v4-pro`.

Structured output: we use JSON *mode* (`response_format={"type": "json_object"}`) for broad
compatibility — it enforces valid JSON *syntax* but not a schema, so we describe the schema in
the prompt and validate/parse the result ourselves.
"""

from __future__ import annotations

import json
from typing import Any

from langsmith.wrappers import wrap_openai
from openai import OpenAI

from nexus_refactor.config import get_settings
from nexus_refactor.llm.base import LLMResult


class DeepSeekProvider:
    name = "deepseek"

    def __init__(self, model: str | None = None) -> None:
        s = get_settings()
        self.model = model or s.deepseek_model
        # Client built here (not at import time) so importing this module never needs a key.
        # wrap_openai makes each LLM call a rich LangSmith span (prompt, completion, tokens) when
        # tracing is on; a transparent no-op otherwise.
        self._client = wrap_openai(
            OpenAI(
                api_key=s.deepseek_api_key or None,
                base_url="https://api.deepseek.com",
            )
        )

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
            text=resp.choices[0].message.content or "",  # content is str | None
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=resp.model,
        )

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, max_tokens: int = 4096
    ) -> dict[str, Any]:
        # JSON mode needs the word "json" in the prompt and enforces *syntax*, not schema — so
        # we describe the schema to the model and validate/parse the result ourselves.
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
