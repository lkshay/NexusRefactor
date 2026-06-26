# Golden set

Hand-curated schema-drift scenarios. **Start at 15-25, not 50** — curating realistic,
compile-able scenarios is real work. Grow it over time and **be honest about N** in any claim.

Each scenario is a directory:

```
my_scenario/
  scenario.yaml        # metadata + ground truth (see fields below)
  openapi_before.yaml  # the spec the downstream code was written against
  openapi_after.yaml   # the changed spec (the drift)
  code/                # the downstream repo in its BROKEN state (mypy/pytest fail here)
    models.py          # "generated from the spec" — already reflects openapi_after
    ...                # hand-written code that still uses the OLD interface
    test_*.py          # localized tests
    conftest.py        # makes pytest treat code/ as the rootdir
  gold_patch.diff      # the reference (minimal) fix — for patch-minimality scoring
```

### Why `code/` ships broken

The realistic framing: a typed model is **auto-generated** from the OpenAPI spec, so it updates
the instant the spec changes. Hand-written code that *uses* that model lags behind. So in the
scenario's starting state, `models.py` already matches `openapi_after`, but the hand-written
usages still reference the old field/endpoint — `mypy` and `pytest` fail out of the box. The
agent's job is to heal those usages. Verify it yourself:

```bash
cd code
uv run mypy --explicit-package-bases .   # error: "User" has no attribute "user_name"  (exit 1)
uv run pytest -q                          # 1 failed: AttributeError                     (exit 1)
```

(`--explicit-package-bases` is only needed when running in-place inside this project; in the
isolated sandbox a plain `mypy .` works. See `src/nexus_refactor/nodes/verify.py`.)

### `scenario.yaml` fields

```yaml
name: example_rename_field
description: One-line summary of the drift.
source: openapi
expected_changes:          # what `parse` should extract (for sanity-checking the parser)
  - kind: field_renamed
    location: components.schemas.User.user_name
    after: username
gold_sites:                # files search SHOULD surface — scores context_recall
  - code/client.py
gold_files:                # files the gold patch touches — scores patch_minimality
  - code/client.py
```

See `example_rename_field/` for a complete, working template. Clone it to make new scenarios.
