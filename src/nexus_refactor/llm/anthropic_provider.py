"""Anthropic implementation of LLMProvider.

>>> STUB — IMPLEMENT when you build the refactor node. <<<
SDK: `anthropic` (already installed). Client: `anthropic.Anthropic(api_key=...)`.

  - complete(): client.messages.create(model, max_tokens, system=system,
                  messages=[{"role": "user", "content": user}]); read resp.content[0].text
                  and resp.usage.{input_tokens, output_tokens}.
  - complete_json(): pass a single tool whose input_schema == your JSON Schema and set
                  tool_choice={"type": "tool", "name": ...}; the model's tool_use input IS
                  your structured object. This is more reliable than asking for raw JSON.
"""

from __future__ import annotations

from typing import Any

from nexus_refactor.config import get_settings
from nexus_refactor.llm.base import LLMResult


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        s = get_settings()
        self.model = model or s.anthropic_model
        # TODO(you): self._client = anthropic.Anthropic(api_key=s.anthropic_api_key)

    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> LLMResult:
        raise NotImplementedError("Implement AnthropicProvider.complete")

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, max_tokens: int = 4096
    ) -> dict[str, Any]:
        raise NotImplementedError("Implement AnthropicProvider.complete_json (tool-use)")
