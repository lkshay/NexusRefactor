"""The `SchemaDelta` — a normalized, provider-agnostic description of an interface change.

This is the *contract* between the `parse` node (which produces it) and the
`search`/`refactor` nodes (which consume it). Keeping it normalized means that when you
add gRPC/protobuf or SQL drift later, the downstream nodes don't change — only the
parser that produces a SchemaDelta changes.

This file is implemented (it's a data model). Extend `ChangeKind` as your golden set grows.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ChangeKind(StrEnum):
    """The kinds of upstream change we model. Start small; grow with the golden set."""

    FIELD_RENAMED = "field_renamed"
    FIELD_REMOVED = "field_removed"
    FIELD_ADDED = "field_added"
    FIELD_TYPE_CHANGED = "field_type_changed"
    FIELD_REQUIRED_CHANGED = "field_required_changed"
    ENDPOINT_RENAMED = "endpoint_renamed"
    ENDPOINT_REMOVED = "endpoint_removed"
    PARAM_CHANGED = "param_changed"


class Change(BaseModel):
    """A single atomic change within the delta."""

    kind: ChangeKind
    # A dotted/pointer-ish path into the spec, e.g. "components.schemas.User.user_name"
    # or "paths./users/{id}.get". Used by `search` to build queries and by metrics to
    # judge whether the right sites were found.
    location: str
    before: str | None = None
    after: str | None = None
    detail: str = ""


class SchemaDelta(BaseModel):
    """The full normalized delta produced by `parse`."""

    source: str = "openapi"  # "openapi" | "grpc" | "sql" — Phase 1 is openapi
    changes: list[Change] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.changes
