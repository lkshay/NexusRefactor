# CLAUDE.md — working notes for this repo

## What this is
NexusRefactor: a LangGraph schema-drift refactoring agent. Phase 1 (build first) = the cyclic
heal loop + hybrid retrieval + eval harness. See `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`,
`docs/DECISIONS.md`.

## This is a LEARNING project — how to help
The owner is building this to learn the foundations and prepare for interviews. **Do not
implement the learning-core logic for them.** Scaffold, explain, review, unblock, and pair —
but the node bodies, retrieval, RRF, and metrics are theirs to write. When asked for help on a
stub: explain the concept and the approach, suggest a structure, review their attempt. Write code
for them only when they explicitly ask for a worked solution.

Already implemented (don't re-teach): `config.py`, `state.py`, `graph.py`, `cli.py`,
`schema/delta.py`, `sandbox/denylist.py`, `sandbox/runner.py` (dev mode), `eval/bootstrap.py`,
`llm/base.py`, the example golden scenario. Everything marked `STUB` / `NotImplementedError` is
the owner's exercise.

## Conventions
- **Package manager: uv.** `uv sync`, `uv run <cmd>`. Never `pip install`. Python pinned to 3.12.
- Run things via the `Makefile` (`make help`). `make run SCENARIO=...`, `make test`, `make eval`,
  `make up` (Qdrant), `make typecheck`, `make lint`, `make fmt`.
- Source layout is `src/` (package `nexus_refactor`), installed editable. `eval/` is a top-level
  package run via `python -m eval.run_eval`.
- Lint/format with ruff; types with mypy (lenient on our src — the strict mypy is the *verify*
  gate run against sample repos, not against this package).

## Non-negotiable: measured, not claimed
No performance/accuracy number gets written into docs, README, or resume lines until it has been
measured on stated hardware, and metrics are reported with a confidence interval and honest N.
See `docs/DECISIONS.md`. If asked to add a benchmark number, push back unless it was measured.

## Gotchas
- **`parse` needs the `oasdiff` binary** (`brew install oasdiff`) — the OpenAPI structural differ;
  the differ unit tests skip if it's missing.
- `uv sync` builds this package editable, which requires `README.md` to exist (it's referenced in
  pyproject). Don't pipe `uv sync` through `tail` — the pipe hides uv's exit code.
- The graph is intentionally runnable with stub nodes; stub `verify` always returns red so the
  bounded-retry gate is exercised. `tests/test_fusion.py` xfails until RRF is implemented.
