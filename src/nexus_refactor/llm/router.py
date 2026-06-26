"""Adaptive provider/model router — the seam for the Phase 3 cost/latency story.

>>> STUB — a simple heuristic now; the measured local-8B-vs-frontier routing comes in Phase 3. <<<

The idea: cheap, mechanical tasks (parsing a structured delta, classifying a change) can go to
a small/local model; hard multi-step reasoning (synthesizing a cross-file patch) goes to a
frontier API. In Phase 1 you only have the two frontier providers, so this just selects between
them (or honors settings.llm_provider). In Phase 3 you add the local vLLM-served 8B as a third
option and MEASURE the token/latency/cost delta — don't predict it.

Keep the return type a `LLMProvider` so callers never branch on the concrete class.
"""

from __future__ import annotations

from nexus_refactor.config import get_settings
from nexus_refactor.llm.anthropic_provider import AnthropicProvider
from nexus_refactor.llm.base import LLMProvider
from nexus_refactor.llm.deepseek_provider import DeepSeekProvider
from nexus_refactor.llm.ollama_provider import OllamaProvider
from nexus_refactor.llm.openai_provider import OpenAIProvider


def choose_provider(task: str = "refactor") -> LLMProvider:
    """Return a provider for the given task label, honoring settings.llm_provider.

    TODO(you): make this adaptive (by task complexity / token estimate / budget remaining).
    For now it just dispatches on the configured provider.
    """
    provider = get_settings().llm_provider
    if provider == "openai":
        return OpenAIProvider()
    if provider == "deepseek":
        return DeepSeekProvider()
    if provider == "ollama":
        return OllamaProvider()
    return AnthropicProvider()
