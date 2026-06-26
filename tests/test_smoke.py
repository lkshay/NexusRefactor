"""Smoke tests: the package imports, config loads, the graph compiles, and the termination
gate behaves.

The gate is tested as a PURE function (should_continue) rather than by invoking the whole
graph: verify now shells out to mypy/pytest and needs a real target_repo, which a fast unit
test shouldn't depend on. (Lesson: implementing a node changed its contract — the gate test
had to stop relying on a no-op verify.)
"""

from __future__ import annotations

from nexus_refactor.config import get_settings
from nexus_refactor.graph import build_graph, should_continue


def test_settings_load() -> None:
    assert get_settings().max_iterations >= 1


def test_graph_compiles() -> None:
    # Catches wiring errors (bad node names, dangling edges) without running real nodes.
    assert build_graph() is not None


# --- termination gate: the safety property (a cyclic graph that can't stop is a hang) ---
def test_gate_done_on_clean() -> None:
    assert should_continue({"build_clean": True, "iteration": 1, "max_iterations": 4}) == "done"


def test_gate_exhausted_on_budget() -> None:
    assert should_continue({"build_clean": False, "iteration": 4, "max_iterations": 4}) == "exhausted"


def test_gate_retries_with_budget_left() -> None:
    assert should_continue({"build_clean": False, "iteration": 2, "max_iterations": 4}) == "retry"
