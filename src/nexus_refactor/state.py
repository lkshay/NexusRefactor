"""The graph's shared memory.

In LangGraph, every node receives the current state and returns a *partial* update
(a dict of just the keys it changed); LangGraph merges it in. For most keys the merge
is "overwrite". For `history` we attach a reducer (operator.add) so updates *append*
instead of overwrite — this is how you accumulate a log across the cyclic heal loop.

`total=False` means every key is optional, so the initial state can omit fields that
later nodes fill in, and each node can return just its slice.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from nexus_refactor.schema.delta import SchemaDelta


class CandidateSite(TypedDict, total=False):
    """One impacted location flagged by `search`."""

    path: str  # file path within target_repo
    symbol: str  # function/class/line that references the changed interface
    score: float  # fused retrieval score
    snippet: str  # the code chunk (context for `refactor`)


class RefactorState(TypedDict, total=False):
    # --- Inputs (set by the CLI before the graph runs) ---
    scenario_dir: str
    target_repo: str  # path to the downstream code the agent may patch
    openapi_before: dict  # parsed YAML
    openapi_after: dict
    max_iterations: int  # the hard cap for the termination gate

    # --- parse node output ---
    schema_diff: SchemaDelta | None
    spec_changed: bool  # zeroth pass: did the spec content change at all? (see openapi_diff)

    # --- search node output ---
    candidate_sites: list[CandidateSite]

    # --- refactor node output ---
    current_patch: str  # unified diff under construction
    iteration: int  # incremented each refactor pass; drives the termination gate
    input_tokens: Annotated[int, operator.add]  # summed across heal iterations (for the metrics store)
    output_tokens: Annotated[int, operator.add]

    # --- verify node output (the objective signal) ---
    compiler_log: str  # mypy output — the "compile" signal in Python
    test_log: str  # pytest output
    build_clean: bool  # True only when BOTH mypy and pytest exit 0

    # --- observability: appended to (note the reducer) ---
    history: Annotated[list[str], operator.add]
    repo_name: str  # the repo name (used for Qdrant payload filtering)