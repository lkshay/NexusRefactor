# NexusRefactor

**An autonomous agent that heals API schema drift.** When an upstream OpenAPI spec changes,
NexusRefactor locates the impacted downstream code, rewrites it, and opens a pull request — but only
after the change passes `mypy` and `pytest`. The self-heal loop is steered by **compiler-grade
signals, not an LLM grading its own work.**

> `LangGraph` cyclic agent · `Qdrant` hybrid retrieval · `mypy`+`pytest` gate · `FastAPI` on `Fly.io` · `LangSmith` tracing

---

## The problem

An upstream service renames a field (`user_name → username`) or changes a type. Every downstream
consumer that still speaks the old shape breaks — often silently, until a test fails or production
throws. The fix is mechanical but tedious: find the call sites, adapt each one, prove nothing else
broke. NexusRefactor automates that, safely, and only ships a change a compiler would accept.

## How it works

<p align="center"><img src="docs/flows-1-end-to-end.svg" width="720" alt="End-to-end data and service flow"></p>

A trigger (a GitHub webhook or the CLI) hands the before/after specs to a **LangGraph** agent that
runs a cyclic loop over a shared, typed state:

- **parse** — structurally diff the two specs with `oasdiff` → a typed `SchemaDelta`.
- **search** — turn the delta into ranked call sites via hybrid retrieval (below).
- **refactor** — the LLM emits `SEARCH/REPLACE` edits; apply them to an isolated working copy.
- **verify** — run `mypy` + `pytest`; `build_clean` is true **only if both exit 0**.
- **gate** — if not clean and the retry budget remains, loop back to `refactor` **with the failure
  logs folded into the prompt** (self-heal); otherwise stop.

Only a green build opens a PR. The bounded retry budget guarantees termination.

## Design decisions

The interesting part isn't that an LLM writes a patch — it's what keeps it honest and reliable.

| Decision | Why |
|---|---|
| Verify with **`mypy` + `pytest` exit codes**, not LLM self-assessment | An objective signal the model can't talk its way past — no reward hacking. The compiler is the judge, not vibes. |
| **Cyclic** agent (LangGraph) with a **bounded** retry budget | The fix is iterative — patch, check, re-patch against the *actual* failure. The loop **is** the product; the budget is the termination guarantee. |
| **Hybrid** retrieval (dense + BM25) fused by **RRF** | Drift is both lexical (the exact renamed identifier) and semantic (the concept it stands for). RRF merges by **rank**, so there's no cosine-vs-BM25 score to normalize. |
| **`SEARCH/REPLACE`** edits, not unified diffs | LLMs reliably botch diff hunks and line numbers; content-anchored blocks apply with a tolerant matcher (exact → whitespace-insensitive → path-recovery). |
| **Working-copy isolation** in `/tmp` for verify | The agent executes code it just wrote; isolation contains the blast radius and sidesteps `mypy`'s duplicate-source error. |
| **Orchestrator / agent split** | The agent returns a *verified patch*; the orchestrator owns git, GitHub, and metrics — so the front door (CLI ↔ webhook ↔ queue) is swappable without touching the agent. |
| **LLM behind a `Protocol`** | Local Ollama for dev, DeepSeek/OpenAI for prod, chosen per task — an adaptive router drops in without a rewrite. |

## Retrieval: hybrid, fused by RRF

<p align="center"><img src="docs/flows-2-retrieval-rrf.svg" width="720" alt="Hybrid retrieval and RRF"></p>

Code is chunked by AST and embedded **twice** — a dense vector (`bge-small`, semantic) and a sparse
BM25 vector (lexical) — into one **Qdrant** collection with named vectors and a `{repo, path, symbol}`
payload for tenant filtering. At query time the changed field is embedded both ways, Qdrant is
searched on each, and the two ranked lists are fused with **Reciprocal Rank Fusion**
(`score = Σ 1/(k + rank)`). Rank-based fusion is what lets a lexical hit and a semantic hit combine
without reconciling incompatible score scales — the right primitive for code search, where you're
chasing an exact renamed identifier *and* the places that use the concept behind it.

## Evaluation: measured, not claimed

This is the discipline the project is built around: **no number is written down until it's measured,
with a confidence interval and an honest N.** (A fabricated benchmark table from the original spec
was deleted — the reasoning is in [DECISIONS.md](docs/DECISIONS.md).)

- **Offline** — a curated golden set of drift scenarios, each run through the full loop. The harness
  reports heal rate, context recall, and patch minimality with **bootstrapped 95% CIs**. The set is
  deliberately small today (N=5), so the intervals are wide and no headline percentage is claimed —
  growing it with more drift kinds is ongoing.
- **Online** — every real run records to a metrics store (heal rate, iterations, latency, token cost,
  recall, and the PR it opened), surfaced at `/metrics`. Offline gates regressions before deploy;
  online measures production. Merge-outcome polling — *did a human accept the PR?*, the north-star —
  is being wired next.

## Deployment & observability

<p align="center"><img src="docs/flows-3-target-architecture.svg" width="760" alt="Target architecture"></p>

The agent is packaged as a container and **deployed on Fly.io** (scale-to-zero) against a managed
**Qdrant Cloud** cluster, with secrets injected at runtime. Two entry points share the same core: a
CLI (`nexus resolve <repo>`) and an **HMAC-verified FastAPI webhook** (GitHub push → background job
→ PR).

Every run is **observed two ways** — because they answer different questions:

- **LangSmith** traces the full run tree: each node plus the LLM's exact prompt and completion —
  *why did it do that?*
- The **metrics store** tracks the KPIs: heal rate, latency, token cost per fix — *is the fleet any
  good?*

*(The agent currently acts via a scoped token; a **GitHub App** identity — a bot login with
least-privilege, short-lived installation tokens — is the next step.)*

## Stack

| | |
|---|---|
| **Orchestration** | LangGraph — cyclic, stateful agent with reducers on shared state |
| **Retrieval** | Qdrant (named dense + sparse vectors, payload filtering) · fastembed (`bge-small-en-v1.5` + `bm25`) · RRF |
| **LLM** | DeepSeek · Ollama · OpenAI — behind an `LLMProvider` `Protocol` |
| **Verification** | `mypy` + `pytest` (the gate) · `oasdiff` (OpenAPI structural diff) |
| **Serving & deploy** | FastAPI + uvicorn · Docker · Fly.io |
| **Observability** | LangSmith (per-run traces) · SQLite→Postgres metrics store |
| **Tooling** | uv · ruff · mypy · Python 3.12 |

## Status

- **Live & measured:** the heal loop, hybrid retrieval, offline + online eval, containerized deploy
  on Fly.io, LangSmith tracing.
- **Next:** GitHub App identity · PR-acceptance polling + a metrics dashboard · a larger, harder eval set.
- **Further out (GPU-gated, measured-only):** a fine-tuned served model + an adaptive local/frontier router.

## Run it

```bash
brew install oasdiff                 # OpenAPI structural differ (used by `parse`)
make sync                            # deps via uv (Python 3.12)
make up                              # local Qdrant (docker)
cp .env.example .env                 # add an LLM key — or run fully local with LLM_PROVIDER=ollama
make run SCENARIO=eval/golden/example_rename_field   # heal one scenario end-to-end (prints its LangSmith trace URL)
make eval                            # the golden-set harness with bootstrapped CIs
```

**Deeper reading:** [ARCHITECTURE.md](docs/ARCHITECTURE.md) (the graph, the verify signal, retrieval) ·
[FLOWS.md](docs/FLOWS.md) (the diagrams + interview narrative) ·
[DECISIONS.md](docs/DECISIONS.md) (the honesty ledger). Core logic lives in
`src/nexus_refactor/nodes/` (the four nodes), `retrieval/` (Qdrant + RRF), and `graph.py` (the state machine).
