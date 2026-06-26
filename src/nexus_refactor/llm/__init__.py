"""LLM access behind a thin provider abstraction.

Both Anthropic and OpenAI are wired from day one (your Phase 1 choice), so the Phase 3
adaptive router has a clean seam to plug into: `router.choose_provider(task)` returns a
provider, and callers depend only on the `LLMProvider` Protocol — never on a concrete SDK.
"""
