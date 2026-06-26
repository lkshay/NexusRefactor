"""Diff two OpenAPI documents.

Two passes, both deterministic (no LLM):
  - `spec_changed` (ZEROTH pass) — did the content change *at all*? Total, lossless dict equality.
  - `diff_openapi` (FIRST pass) — categorize the change into a `SchemaDelta`.

`diff_openapi` shells out to **oasdiff** (the standard OpenAPI-diff tool) for a complete, robust
structural diff: it recurses through nested schemas, resolves `$ref`s, and reports type / format /
enum / required changes that a hand-rolled differ misses. We map oasdiff's `components.schemas`
diff onto our `SchemaDelta`.

oasdiff does NOT guess renames — a rename appears as a removed + an added property, and
`refactor`'s LLM infers the rename from context. That's deliberately more robust than the brittle
type-match heuristic this used to use.

Requires the `oasdiff` binary on PATH (`brew install oasdiff`). Not yet mapped (oasdiff provides
them — extend when a scenario needs it): inline request/response bodies defined under `paths`
(rather than `$ref`'d from components.schemas), and parameter changes.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import yaml

from nexus_refactor.schema.delta import Change, ChangeKind, SchemaDelta


def spec_changed(before: dict, after: dict) -> bool:
    """Zeroth pass: did the spec CONTENT change at all?

    Compares the PARSED structures (not raw bytes), so it ignores formatting, key order, and
    comments. It's *total*: any real content change makes this True, which is what lets it catch
    changes `diff_openapi` doesn't model yet (the gap between the two = this differ's blind spot).
    """
    return before != after


def diff_openapi(before: dict, after: dict) -> SchemaDelta:
    """Return the normalized delta between two parsed OpenAPI specs, via oasdiff."""
    raw = _run_oasdiff(before, after)
    changes: list[Change] = []
    _diff_schemas(raw, changes)
    _diff_paths(raw, changes)
    return SchemaDelta(source="openapi", changes=changes)


def _run_oasdiff(before: dict, after: dict) -> dict:
    """Write both specs to temp files and run `oasdiff diff -f json`."""
    with tempfile.TemporaryDirectory() as d:
        bp, ap = Path(d) / "before.yaml", Path(d) / "after.yaml"
        bp.write_text(yaml.safe_dump(before))
        ap.write_text(yaml.safe_dump(after))
        try:
            proc = subprocess.run(
                ["oasdiff", "diff", "-f", "json", str(bp), str(ap)],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "oasdiff not found on PATH — install it with `brew install oasdiff`"
            ) from exc
    if proc.returncode != 0:
        raise RuntimeError(f"oasdiff failed ({proc.returncode}): {proc.stderr.strip()}")
    return json.loads(proc.stdout or "{}")


def _diff_schemas(raw: dict, changes: list[Change]) -> None:
    modified = raw.get("components", {}).get("schemas", {}).get("modified", {})
    for name, schema_diff in modified.items():
        _walk_schema(f"components.schemas.{name}", schema_diff, changes)


def _walk_schema(base: str, node: dict, changes: list[Change]) -> None:
    """Recursively map one oasdiff schema-diff node onto Change records."""
    props = node.get("properties", {})
    added = props.get("added", []) or []
    deleted = props.get("deleted", []) or []
    modified = props.get("modified", {}) or {}

    for name in deleted:
        changes.append(Change(kind=ChangeKind.FIELD_REMOVED, location=f"{base}.{name}", before=name))
    for name in added:
        changes.append(Change(kind=ChangeKind.FIELD_ADDED, location=f"{base}.{name}", after=name))

    # required-ness changes — only for fields that still exist (add/remove already covers the rest)
    req = node.get("required", {})
    for name in set(req.get("added", []) or []) - set(added):
        changes.append(
            Change(kind=ChangeKind.FIELD_REQUIRED_CHANGED, location=f"{base}.{name}",
                   before="optional", after="required")
        )
    for name in set(req.get("deleted", []) or []) - set(deleted):
        changes.append(
            Change(kind=ChangeKind.FIELD_REQUIRED_CHANGED, location=f"{base}.{name}",
                   before="required", after="optional")
        )

    for name, mod in modified.items():
        loc = f"{base}.{name}"
        if "type" in mod:
            t = mod["type"]
            changes.append(
                Change(kind=ChangeKind.FIELD_TYPE_CHANGED, location=loc,
                       before=str((t.get("deleted") or [""])[0]), after=str((t.get("added") or [""])[0]))
            )
        if "format" in mod:
            fmt = mod["format"]
            changes.append(
                Change(kind=ChangeKind.FIELD_TYPE_CHANGED, location=loc,
                       before=str(fmt.get("from")), after=str(fmt.get("to")), detail="format")
            )
        if "properties" in mod:  # nested object/schema — recurse
            _walk_schema(loc, mod, changes)


def _diff_paths(raw: dict, changes: list[Change]) -> None:
    for p in raw.get("paths", {}).get("deleted", []) or []:
        changes.append(Change(kind=ChangeKind.ENDPOINT_REMOVED, location=f"paths.{p}", before=p))
