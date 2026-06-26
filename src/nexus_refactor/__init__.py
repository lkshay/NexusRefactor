"""NexusRefactor — a schema-drift refactoring agent built on LangGraph.

Takes an upstream interface change (OpenAPI/REST in Phase 1), finds every downstream
call site via hybrid retrieval, and iteratively patches -> type-checks -> tests until
the build is clean. The self-heal loop is gated by mypy/pytest exit codes (objective)
and a bounded retry budget (it cannot spin forever).

See docs/ARCHITECTURE.md for the design and docs/ROADMAP.md for what to implement next.
"""

__version__ = "0.1.0"
