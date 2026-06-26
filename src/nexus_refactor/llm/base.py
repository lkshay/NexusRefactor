"""The provider-agnostic LLM interface. Implemented (it's the contract).

Concrete providers (anthropic_provider, openai_provider) implement this Protocol. Nodes and
the router depend ONLY on `LLMProvider` — that's what makes the local/frontier routing in
Phase 3 a drop-in rather than a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMResult:
    """Normalized result. Token counts feed the budget gate and LangSmith cost tracking."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal surface the agent needs. Keep it small; grow only when a node demands it."""

    name: str

    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> LLMResult:
        """Free-form completion (used by the refactor node to draft a diff)."""
        ...

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, max_tokens: int = 4096
    ) -> dict[str, Any]:
        """Structured output constrained to `schema` (JSON Schema).

        Anthropic: implement via tool-use with the schema as the tool's input_schema.
        OpenAI:    implement via response_format json_schema (Structured Outputs).
        Returns the parsed object. This is where Phase 2's Guardrails-AI validation will hook in.
        """
        ...
