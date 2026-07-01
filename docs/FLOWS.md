# Data & service flows

How a schema change becomes a verified pull request, and the retrieval that powers it.
This is the interview-prep reference: trace the flow out loud, then be ready for the "why" behind
each decision. See also [ARCHITECTURE.md](ARCHITECTURE.md) and [DECISIONS.md](DECISIONS.md).

## 1. End-to-end flow

![End-to-end data and service flow](flows-1-end-to-end.svg)

A spec changes → a **trigger** (a GitHub webhook, HMAC-verified, or the CLI) calls
**`resolve_drift`**, which pulls the *before* spec from git and the *after* from the working tree,
indexes the code into Qdrant, cuts a branch, and **invokes the graph**. Inside the agent:

- **`parse`** diffs the two specs (oasdiff) into a `schema_diff`.
- **`search`** turns that into ranked `candidate_sites` via hybrid retrieval (see §2).
- **`refactor`** asks the LLM for SEARCH/REPLACE edits and applies them to a working copy.
- **`verify`** runs mypy + pytest in an isolated `/tmp` copy and sets `build_clean` from their
  **exit codes**.
- A **gate** loops back to `refactor` with the failure logs until it's green or the iteration
  budget runs out.

On green, `resolve_drift` commits, opens a PR via `gh`, and **`record_run`** writes one metrics row.

### The data shape at each hop

| hop | in → out |
|---|---|
| parse | `(openapi_before, openapi_after)` dicts → `SchemaDelta{ changes:[{kind, location, before, after}] }` |
| search | `SchemaDelta` → `candidate_sites:[{path, symbol, snippet, score}]` |
| refactor | `sites + delta + prev logs` → SEARCH/REPLACE blocks → applied files + `current_patch` (unified diff) |
| verify | patched working copy → `(compiler_log, test_log, build_clean:bool)` |
| gate | `build_clean, iteration` → `refactor` \| `END` |

`RefactorState` is a shared `TypedDict`; every node returns a *partial* update that LangGraph merges.
`history` and the token counters use `operator.add` reducers, so they **accumulate** across every
loop iteration instead of overwriting.

## 2. Hybrid retrieval + RRF (inside `search`)

![Hybrid retrieval and reciprocal rank fusion](flows-2-retrieval-rrf.svg)

- **Index path** (at setup, before the agent): code is chunked by AST (functions/classes), each
  chunk is embedded **twice** — a dense `bge-small` 384-d vector and a sparse `bm25` vector — and
  upserted as one Qdrant point carrying both **named vectors** + a payload `{repo, path, symbol, code}`.
- **Query path** (per changed field): the field name is embedded with the same two models, Qdrant is
  searched **twice** (repo-filtered), and the two ranked lists are fused by **RRF**:

  ```
  score(d) = Σ  1 / (k + rank_list(d))     (k ≈ 60)
  ```

RRF merges the **lexical** bm25 hit (exact field-name match) and the **semantic** dense hit by
**rank**, so there's no need to normalize a cosine score against a bm25 score.

## 3. Target deployment (the pitch)

![Target architecture](flows-3-target-architecture.svg)

An org installs the GitHub App on its repos. A spec change → GitHub delivers a webhook + an App
installation token → the agent service on **Fly.io** heals the downstream code (gated by mypy +
pytest) → a **verified PR** goes back for a human to review and merge. Observability is two layers:
**LangSmith** for per-run traces (*why* did this run do that?) and a separate **online-eval
dashboard** for the KPIs — heal rate, $/PR, and **PR-acceptance** (polled back from GitHub).

Backing services: cloud **Qdrant** (retrieval) and **DeepSeek** (LLM). The agent, container, and
eval harness exist today; the Fly host, App identity, cloud Qdrant, and LangSmith wiring are the
deploy steps that make this picture real.

## 4. The design decisions interviewers probe

- **Why a cyclic graph, not a linear pipeline?** The fix is iterative — patch, check, re-patch
  against the failure. The self-heal loop *is* the product.
- **Why mypy + pytest exit codes as the gate (not the LLM judging itself)?** An **objective** signal
  the model can't talk its way past. No reward-hacking. It's the Python analog of "does it compile
  and pass tests." *(Lead with this one.)*
- **Why hybrid retrieval + RRF, not just a vector search?** A field rename is a *lexical* event —
  bm25 nails the exact token; dense catches semantic paraphrase. RRF fuses them by rank, so you never
  reconcile incompatible score scales.
- **Why SEARCH/REPLACE blocks, not unified diffs?** LLMs reliably botch diff line numbers.
  Anchor-on-content blocks apply with a tolerant matcher (exact → whitespace-insensitive →
  path-recovery), which is why the heal rate is robust.
- **Why a `/tmp` working copy for verify?** Isolation (the agent never mutates source) *and* it
  sidesteps mypy's "source file found twice" when run nested in a project.
- **Why split `resolve_drift` (orchestrator) from the graph (agent)?** Separation of concerns: the
  agent produces a *verified patch*; the orchestrator owns git, GitHub, and metrics. Swap the front
  door (CLI ↔ webhook ↔ queue) without touching the agent.
- **What guarantees termination?** The bounded-retry gate (`iteration ≥ max → END`).

Two follow-ups worth having ready: the index is **per-repo** (payload-filtered, so multi-tenant-ready),
and nothing opens a PR unless the build is **green** — that verify signal is why this is safer than a
plain code-gen tool.
