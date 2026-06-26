"""OpenAI implementation of LLMProvider.

>>> STUB — IMPLEMENT when you build the refactor node. <<<
SDK: `openai` (already installed). Client: `openai.OpenAI(api_key=...)`.

  - complete(): client.chat.completions.create(model, messages=[{system},{user}],
                  max_tokens=...); read choice.message.content and resp.usage.
  - complete_json(): use Structured Outputs — response_format={"type":"json_schema",
                  "json_schema":{"name":..., "schema": schema, "strict": True}} — and parse
                  the returned JSON. Keeps you symmetric with the Anthropic provider.
"""

from __future__ import annotations

from typing import Any

from nexus_refactor.config import get_settings
from nexus_refactor.llm.base import LLMResult


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        s = get_settings()
        self.model = model or s.openai_model
        # TODO(you): self._client = openai.OpenAI(api_key=s.openai_api_key)

    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> LLMResult:
        raise NotImplementedError("Implement OpenAIProvider.complete")

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, max_tokens: int = 4096
    ) -> dict[str, Any]:
        raise NotImplementedError("Implement OpenAIProvider.complete_json (structured outputs)")
