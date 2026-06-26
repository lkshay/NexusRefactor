# NexusRefactor

A **schema-drift refactoring agent** built on **LangGraph**. Give it an upstream interface
change (Phase 1: an OpenAPI/REST spec edit); it finds every impacted downstream call site via
**hybrid retrieval** (dense + BM25, fused with RRF on Qdrant), then iteratively
**patches → type-checks → tests** until the build is clean — or until a bounded retry budget
runs out.

The self-heal loop is steered by an **objective signal** — `mypy` + `pytest` exit codes — not
an LLM grading itself. That is the whole thesis: ground the loop in the compiler, not in vibes.

> This repo is a **learning scaffold**. The graph runs end-to-end today with stub nodes; you
> implement the real logic incrementally. Start at [docs/ROADMAP.md](docs/ROADMAP.md).

## Quickstart

```bash
brew install oasdiff      # external dep: OpenAPI structural differ (used by `parse`)
make sync                 # install deps into .venv (uv, Python 3.12)
make up                   # start local Qdrant (docker)
cp .env.example .env      # fill in API keys when you reach the refactor/search nodes
make run SCENARIO=eval/golden/example_rename_field   # run the (stub) agent on a scenario
make show-graph           # or: uv run nexus show-graph  -> prints the graph as Mermaid
make test                 # smoke tests pass; the RRF tests xfail until you implement fusion
```

The skeleton run will loop `refactor → verify` until it hits `max_iterations` and stop — that
is the **termination gate** working before any real logic exists. Your job is to make each node
real so the loop actually heals the build.

## Phase map (honest scope)

| Phase | What | Status |
| --- | --- | --- |
| **1 — Core** | LangGraph heal loop, hybrid retrieval, eval harness w/ bootstrapped CIs, minimal sandbox + LangSmith | **build first** |
| **2 — Deploy** | FastAPI service, Docker → App Runner → Terraform, k6 load test, full Guardrails-AI | later |
| **3 — Serving** | QLoRA (Unsloth) 8B + vLLM, adaptive local/frontier router — **GPU-gated, measured-only** | gated |

See [docs/DECISIONS.md](docs/DECISIONS.md) for the pillar honesty audit and the
**measured-not-claimed** discipline (no number gets written down until it has been measured).

## Repo map

```
src/nexus_refactor/
  graph.py            # the LangGraph state machine (wired; runnable)  ← read this first
  state.py            # shared memory (TypedDict + a reducer)
  config.py           # settings from .env (implemented)
  cli.py              # `nexus run` (implemented)
  schema/             # SchemaDelta model (done) + openapi_diff (STUB)
  nodes/              # parse / search / refactor / verify  (STUBS you implement)
  retrieval/          # qdrant_store / indexer / fusion(RRF)  (STUBS)
  sandbox/            # runner (STUB) + denylist (starter implemented)
  llm/                # provider Protocol (done) + anthropic/openai/router (STUBS)
eval/
  golden/             # curated scenarios; example_rename_field is a complete template
  metrics.py          # patch minimality / compile success / context recall (STUBS)
  bootstrap.py        # bootstrapped 95% CI (implemented — reference)
  run_eval.py         # harness (STUB)
docs/                 # ROADMAP, ARCHITECTURE, DECISIONS
```

## Why these choices

- **LangGraph** — the cyclic, stateful heal loop is the reason. A linear pipeline wouldn't need it.
- **Qdrant** — native sparse + dense vectors and payload filtering in one store; the right fit
  for code search where exact identifier matching (BM25) and semantic intent (dense) both matter.
- **mypy + pytest as the "compiler"** — Python has no compile step; this is the honest analog of
  compiler exit codes for schema drift. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
