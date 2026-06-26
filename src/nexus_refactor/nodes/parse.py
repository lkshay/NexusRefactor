"""parse: upstream OpenAPI change -> structured SchemaDelta.

Runs two passes (both in schema/openapi_diff.py): the zeroth pass `spec_changed` (did anything
change at all?) then the first pass `diff_openapi` (what changed, categorized). When the spec
changed but the delta is empty, that's a differ blind spot — surfaced here for triage and eval.
"""

from __future__ import annotations

from nexus_refactor.schema.openapi_diff import diff_openapi, spec_changed
from nexus_refactor.state import RefactorState


def parse_node(state: RefactorState) -> dict:
    before, after = state["openapi_before"], state["openapi_after"]
    changed = spec_changed(before, after)  # zeroth pass: total
    delta = diff_openapi(before, after)  # first pass: categorized

    if not changed:
        note = "no spec change — any downstream failure is out of scope for drift"
    elif delta.is_empty():
        note = "spec CHANGED but delta empty — differ blind spot (LLM-fallback candidate)"
    else:
        note = ", ".join(c.kind.value for c in delta.changes)

    return {
        "schema_diff": delta,
        "spec_changed": changed,
        "history": [f"parse: changed={changed}, {len(delta.changes)} change(s) [{note}]"],
    }
