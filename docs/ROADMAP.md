# Roadmap — what to implement, in order

The scaffold runs today with stub nodes. You make it real one piece at a time. Each item lists
the **file**, the **concept** you're learning, and a **done-when** check. Tackle them top-down.

## Milestone A — "the loop heals one real scenario" (Phase 1a + minimal 1b)

The fastest path to a working agent is to get an objective signal first, then feed it.

- [ ] **1. `verify` node** — `nodes/verify.py` + `sandbox/runner.py`
  - *Concept:* grounding the loop in `mypy` + `pytest` exit codes (not self-judgment).
  - *Done when:* on `eval/golden/example_rename_field/code`, verify returns `build_clean=False`
    as-is, and `True` after you manually apply the fix (`user.user_name` → `user.username`).

- [ ] **2. `openapi_diff` + `parse` node** — `schema/openapi_diff.py`, `nodes/parse.py`
  - *Concept:* deterministic structured delta (no LLM where you don't need one).
  - *Done when:* parse emits a `FIELD_RENAMED` Change for the example scenario.

- [ ] **3. RRF** — `retrieval/fusion.py`
  - *Concept:* rank-based fusion, scale-invariance. *Done when:* `tests/test_fusion.py` passes
    (then delete the `xfail` markers).

- [ ] **4. Retrieval store + indexer** — `retrieval/qdrant_store.py`, `retrieval/indexer.py`
  - *Concept:* structural chunking, named dense+sparse vectors, payload filtering.
  - *Done when:* `make up` then `python scripts/index_repo.py .../code --repo example`, and a
    hybrid search for `"user_name"` ranks `client.py` first.

- [ ] **5. `search` node** — `nodes/search.py`
  - *Done when:* `candidate_sites` contains `client.py` for the example.

- [ ] **6. LLM providers** — `llm/anthropic_provider.py`, `llm/openai_provider.py`
  - *Concept:* one interface, two SDKs; structured output via tool-use / json_schema.
  - *Done when:* a one-off `complete("say hi","")` returns text for each (needs API keys in `.env`).

- [ ] **7. `refactor` node** — `nodes/refactor.py`
  - *Concept:* the heal step — and feeding the prior failure log back in on retries.
  - *Done when:* `make run SCENARIO=eval/golden/example_rename_field` reaches `CLEAN BUILD`
    within the budget.

## Milestone B — eval rigor (Phase 1c)

- [ ] **8. Metrics** — `eval/metrics.py` (`patch_minimality`, `context_recall`; `compilation_success` is done).
- [ ] **9. Harness** — `eval/run_eval.py` (wire scoring; aggregation + CIs already there).
  - *Done when:* `make eval` prints all three metrics with bootstrapped 95% CIs and honest N.
- [ ] **10. Grow the golden set** to 15-25 scenarios. Clone `example_rename_field`. Vary the
      `ChangeKind` (removal, type change, endpoint rename) and the number of impacted sites.

## Milestone C — instrumentation + safety (Phase 1d)

- [ ] **11. LangSmith** — set `LANGSMITH_TRACING=true` + key in `.env`; confirm traces show every
      node, LLM call, and tool exec, with token cost per heal iteration.
- [ ] **12. Container isolation** — implement `isolated=True` in `sandbox/runner.py`; switch
      `verify` to use it. Now you're not running LLM-touched code on the host.

## Phase 2 — deployment + scale evidence (later)

`uv sync --extra phase2` to pull FastAPI/uvicorn/locust/guardrails.

- [ ] FastAPI wrapper (async, connection pooling, rate limit, circuit breaker on the LLM API).
- [ ] Docker → AWS App Runner → Terraform (IaC); managed Qdrant + Postgres.
- [ ] Load test with k6/Locust; commit p50/p95/p99 + RPS. **Put the scale claim in measured
      numbers**, not in "configured autoscaling" (App Runner autoscales for you).
- [ ] Guardrails-AI structured-output/tool-arg validation; write `SECURITY.md` threat model.

## Phase 3 — inference serving (GPU-gated, measured-only)

Do this **only with a GPU** and **only to produce real numbers**. State the hardware.

- [ ] QLoRA fine-tune (Unsloth) of an 8B for structured function-calling.
- [ ] Serve with vLLM (PagedAttention, continuous batching, guided decoding).
- [ ] Make `llm/router.py` adaptive: simple extractions → local 8B; complex refactors → frontier.
- [ ] Measure token / latency / cost delta **including amortized GPU + training cost**. At low
      volume self-hosting may cost *more* — say so; the win is at sustained throughput.

> Resume lines are licensed only *after* the work exists. The list lives in the build spec; don't
> write a number down until you've measured it. See [DECISIONS.md](DECISIONS.md).
