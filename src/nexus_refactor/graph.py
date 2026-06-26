"""The LangGraph state machine — wired and runnable, even with stub nodes.

This file is implemented so you can `make run` on day one and watch the loop execute.
What you fill in over time is the *node bodies* (see src/nexus_refactor/nodes/).

Topology:

    START -> parse -> search -> refactor -> verify -> [should_continue?]
                                   ^                          |
                                   |   retry (build red)      |
                                   +--------------------------+
                                                              |
                                              done / exhausted -> END

The back-edge from `verify` to `refactor` is the cycle. A linear pipeline would not need
LangGraph at all — the framework earns its place precisely because of this loop, and the
loop is made safe by `should_continue`, the bounded-retry termination gate.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from nexus_refactor.nodes import parse, refactor, search, verify
from nexus_refactor.state import RefactorState


def should_continue(state: RefactorState) -> str:
    """Conditional edge after `verify`. THE termination gate.

    Three outcomes:
      - "done":      build is clean -> stop, success.
      - "exhausted": retry budget hit -> stop, failure (do NOT loop forever).
      - "retry":     build is red and budget remains -> loop back to refactor.
    """
    if state.get("build_clean"):
        return "done"
    if state.get("iteration", 0) >= state.get("max_iterations", 4):
        return "exhausted"
    return "retry"


def build_graph():
    """Construct and compile the graph.

    Later (Phase 1d) you can pass a checkpointer to `.compile(checkpointer=...)` to make
    runs resumable and to inspect state at each step — useful with LangSmith tracing.
    """
    g = StateGraph(RefactorState)

    g.add_node("parse", parse.parse_node)
    g.add_node("search", search.search_node)
    g.add_node("refactor", refactor.refactor_node)
    g.add_node("verify", verify.verify_node)

    # Linear spine
    g.add_edge(START, "parse")
    g.add_edge("parse", "search")
    g.add_edge("search", "refactor")
    g.add_edge("refactor", "verify")

    # Conditional self-heal cycle + termination gate
    g.add_conditional_edges(
        "verify",
        should_continue,
        {
            "done": END,
            "exhausted": END,
            "retry": "refactor",
        },
    )

    return g.compile()
