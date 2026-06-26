# Decisions & honesty ledger

This file is the project's conscience. The whole point of NexusRefactor is to build the kind of
system that catches overclaims — so it must not make any.

## The discipline: measured, not claimed

**No number gets written down until it has been measured on stated hardware.** The original spec
shipped a benchmark table (93.7% token reduction, 17x TTFT, 100% compliance, 94% cost win) for a
system that didn't exist — every figure labeled "measured." That table is **deleted**. Two of its
numbers were also wrong on the merits:

- *850ms → 50ms TTFT*: compared a frontier API to a local 8B — apples to oranges. 50ms is a
  hardware property, not an architecture win.
- *94% cost*: ignored amortized GPU + fine-tuning cost, which at low volume usually makes
  self-hosting **more** expensive, not less.

Resume lines (in the build spec) are licensed **only after** the corresponding work exists, and
any metric is reported **with a confidence interval and an honest N**.

## Pillar honesty audit (from the build spec)

| Pillar | Status | Why |
| --- | --- | --- |
| LangGraph state machine | Keep — core | The compile-test-heal loop is the defensible heart. It's a *cyclic stateful graph*, never a "cyclic DAG". |
| Hybrid search (Qdrant) | Keep — upgrade | Dense + BM25 + RRF is the correct choice for code search where exact identifier matching matters. |
| Observability (LangSmith) | Keep — cheap | Native to LangGraph, low friction. Phase 1d. |
| Guardrails / sandboxing | Keep — split | Minimal isolation is mandatory in Phase 1 (it runs code). Full Guardrails-AI + threat model is Phase 2. |
| Eval loop | Keep — core | The differentiator. Add statistical rigor: bootstrapped CIs, honest dataset size. |
| vLLM / QLoRA / Unsloth | Defer — Phase 3 | Justified, but multi-week and GPU-gated; numbers must be measured on real hardware. |

## Decisions made at setup (2026-06-23)

- **Target language = Python.** Fastest heal loop; verify built behind a pluggable interface so
  C++/Go can drop in later. The "multi-language" resume line is earned later, not now.
- **Schema type = OpenAPI/REST** for the first golden scenarios. (Protobuf/gRPC and SQL remain
  natural extensions — `SchemaDelta.source` already anticipates them.)
- **LLM providers = both** (Anthropic + OpenAI) behind a thin `LLMProvider` Protocol from day
  one, so the Phase 3 adaptive router is a drop-in, not a rewrite.
- **Tooling = uv + Python 3.12.** System Python is 3.14, too new for parts of the ML stack; uv
  pins 3.12 for clean resolution.
- **Embeddings = local fastembed** (no API cost during dev). Swap to a code-specialized model
  once you've *measured* that it improves context recall.
- **Verify signal = mypy + pytest exit codes** as the Python analog of compiler exit codes
  (see ARCHITECTURE.md).
- **Zeroth pass before the differ.** `parse` first runs `spec_changed` (deep equality of the
  parsed specs) — a total, lossless "did anything change?" — then the categorizing `diff_openapi`.
  `changed=True` with an empty delta = a differ blind spot (a change kind we don't model yet); it
  separates case B (differ gap) from case C (no drift at all) and is a natural LLM-escalation
  hook. Caveat: dict equality is order-sensitive on lists (e.g. a `required` reorder), which can
  raise a false gap flag — canonicalize order-insensitive lists if that noise matters. Worth
  tracking as a "differ change-detection coverage" metric in eval.

## Open questions to resolve as you build

- Patch-minimality distance metric — pick one and define it here once chosen (eval/metrics.py).
- Rename detection in `openapi_diff` is heuristic (a removed + added field of the same type).
  Note its false-positive rate in your eval rather than assuming it's right.
- Allowlist vs denylist for the sandbox — start denylist, move to allowlist when comfortable.
