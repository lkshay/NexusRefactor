"""Tests for the oasdiff-backed differ. Need the `oasdiff` binary; skipped if it's missing."""

from __future__ import annotations

import shutil

import pytest

from nexus_refactor.schema.delta import ChangeKind
from nexus_refactor.schema.openapi_diff import diff_openapi, spec_changed

pytestmark = pytest.mark.skipif(shutil.which("oasdiff") is None, reason="needs the oasdiff binary")


def _spec(properties: dict, required: list[str]) -> dict:
    return {
        "openapi": "3.0.3",
        "info": {"title": "T", "version": "1.0.0"},
        "paths": {},
        "components": {
            "schemas": {"Thing": {"type": "object", "properties": properties, "required": required}}
        },
    }


def test_rename_is_remove_plus_add() -> None:
    # oasdiff doesn't guess renames — refactor's LLM infers it from removed + added.
    changes = diff_openapi(
        _spec({"user_name": {"type": "string"}}, ["user_name"]),
        _spec({"username": {"type": "string"}}, ["username"]),
    ).changes
    leaves = {(c.kind, c.location.rsplit(".", 1)[-1]) for c in changes}
    assert (ChangeKind.FIELD_REMOVED, "user_name") in leaves
    assert (ChangeKind.FIELD_ADDED, "username") in leaves
    assert not any(c.kind is ChangeKind.FIELD_RENAMED for c in changes)


def test_type_change() -> None:
    changes = diff_openapi(
        _spec({"total": {"type": "string"}}, ["total"]),
        _spec({"total": {"type": "number"}}, ["total"]),
    ).changes
    assert any(
        c.kind is ChangeKind.FIELD_TYPE_CHANGED and c.before == "string" and c.after == "number"
        for c in changes
    )


def test_removal() -> None:
    changes = diff_openapi(
        _spec({"a": {"type": "string"}, "b": {"type": "integer"}}, ["a"]),
        _spec({"a": {"type": "string"}}, ["a"]),
    ).changes
    removed = [c for c in changes if c.kind is ChangeKind.FIELD_REMOVED]
    assert removed and removed[0].before == "b"


def test_required_change() -> None:
    changes = diff_openapi(
        _spec({"a": {"type": "string"}}, []),
        _spec({"a": {"type": "string"}}, ["a"]),
    ).changes
    assert any(
        c.kind is ChangeKind.FIELD_REQUIRED_CHANGED and c.before == "optional" and c.after == "required"
        for c in changes
    )


def test_nested_type_change_recurses() -> None:
    nested = lambda t: {"nested": {"type": "object", "properties": {"x": {"type": t}}}}  # noqa: E731
    changes = diff_openapi(_spec(nested("string"), []), _spec(nested("integer"), [])).changes
    assert any(
        c.kind is ChangeKind.FIELD_TYPE_CHANGED and c.location.endswith("nested.x") for c in changes
    )


def test_identical_specs_yield_empty_delta() -> None:
    spec = _spec({"a": {"type": "string"}}, ["a"])
    assert diff_openapi(spec, spec).is_empty()


def test_spec_changed_zeroth_pass() -> None:
    spec = _spec({"a": {"type": "string"}}, ["a"])
    assert spec_changed(spec, spec) is False
    assert spec_changed(spec, _spec({"a": {"type": "integer"}}, ["a"])) is True


def test_blind_spot_change_outside_differ_scope() -> None:
    # only info.version differs — oasdiff sees it, but our mapping ignores info, so the delta is
    # empty while spec_changed is True. That mismatch is the blind-spot signal.
    schemas = {"components": {"schemas": {"Thing": {"type": "object", "properties": {"a": {"type": "string"}}}}}}
    before = {"openapi": "3.0.3", "info": {"version": "1.0.0"}, "paths": {}, **schemas}
    after = {"openapi": "3.0.3", "info": {"version": "2.0.0"}, "paths": {}, **schemas}
    assert spec_changed(before, after) is True
    assert diff_openapi(before, after).is_empty()
