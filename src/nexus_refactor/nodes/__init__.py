"""Graph nodes. Each module exposes one `*_node(state) -> dict` function.

A node receives the full RefactorState and returns a PARTIAL update (only the keys it
changed). LangGraph merges that update into the state. Keep nodes small and single-purpose.

Implementation order (see docs/ROADMAP.md):
  1. verify   — get an objective signal first (mypy + pytest). Everything else serves this.
  2. parse    — wire up schema/openapi_diff.diff_openapi.
  3. search   — wire up the Qdrant hybrid retriever.
  4. refactor — the LLM patch generation (do this last; it depends on the other three).
"""
