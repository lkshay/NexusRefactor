"""Tests for the SchemaDelta model (which is implemented) — a green example to pattern-match."""

from __future__ import annotations

from nexus_refactor.schema.delta import Change, ChangeKind, SchemaDelta


def test_empty_delta() -> None:
    d = SchemaDelta()
    assert d.is_empty()
    assert d.source == "openapi"


def test_delta_with_change() -> None:
    change = Change(
        kind=ChangeKind.FIELD_RENAMED,
        location="components.schemas.User.user_name",
        after="username",
    )
    d = SchemaDelta(changes=[change])
    assert not d.is_empty()
    assert d.changes[0].kind is ChangeKind.FIELD_RENAMED
