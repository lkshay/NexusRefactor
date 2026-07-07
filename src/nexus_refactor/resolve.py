"""`nexus resolve` — fix schema drift in a real git repo and open a PR.

The production-shaped entry point. Point it at a repo whose OpenAPI spec just changed: it runs the
agent on a fix branch, and if mypy + pytest go green, it commits and opens a PR via `gh`. That's
the "autonomous agent resolves a ticket end-to-end, gated by CI" surface — the same graph as the
fixture CLI, wrapped in git + GitHub instead of a /tmp working copy.

before-spec = the spec at `base` (default HEAD~1); after-spec = the current working tree.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import yaml
from qdrant_client.models import FieldCondition, Filter, MatchValue

from nexus_refactor.config import get_settings
from nexus_refactor.graph import build_graph
from nexus_refactor.metrics_store import provider_and_model, record_run
from nexus_refactor.retrieval.indexer import chunk_repo
from nexus_refactor.retrieval.qdrant_store import (
    COLLECTION,
    ensure_collection,
    get_client,
    index_chunks,
)
from nexus_refactor.schema.openapi_diff import diff_openapi


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(cmd)}` failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def resolve_drift(
    repo: str,
    spec: str = "openapi.yaml",
    code_dir: str = "service",
    base: str = "HEAD~1",
    branch: str = "nexus/schema-drift-fix",
    open_pr: bool = True,
    token: str | None = None,
) -> dict:
    """Run the agent on a git repo's drift; return {healed, history, diff, pr_url}.

    `token`: a GitHub App installation token (webhook path) so `gh` opens the PR as the scoped bot;
    None (the CLI path) uses the ambient gh/git credentials.
    """
    settings = get_settings()
    repo_path = Path(repo).resolve()
    code_path = repo_path / code_dir
    repo_name = repo_path.name

    before = yaml.safe_load(_run(["git", "show", f"{base}:{spec}"], repo_path))
    after = yaml.safe_load((repo_path / spec).read_text())

    # index the consuming code so `search` can find the call sites
    client = get_client()
    ensure_collection(client)
    client.delete(
        COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="repo", match=MatchValue(value=repo_name))]
        ),
    )
    index_chunks(client, chunk_repo(code_path, repo_name))

    # work on a fresh fix branch off the current HEAD (the drift)
    _run(["git", "checkout", "-B", branch], repo_path)

    start = time.perf_counter()
    final = build_graph().invoke(
        {
            "scenario_dir": str(repo_path),
            "target_repo": str(code_path),
            "repo_name": repo_name,
            "openapi_before": before,
            "openapi_after": after,
            "iteration": 0,
            "max_iterations": settings.max_iterations,
            "history": [],
        }
    )
    latency_ms = int((time.perf_counter() - start) * 1000)

    result: dict = {
        "healed": bool(final.get("build_clean")),
        "history": final.get("history", []),
        "diff": "",
        "pr_url": None,
    }
    if not result["healed"]:
        _run(["git", "checkout", "--", "."], repo_path)  # discard partial edits, keep branch
        _record(repo_name, final, latency_ms, result)
        return result

    result["diff"] = _run(["git", "diff"], repo_path)
    _run(["git", "add", "-A"], repo_path)
    _run(["git", "commit", "-m", "fix: resolve schema drift in downstream code"], repo_path)

    if open_pr:
        gh_env = {**os.environ, "GH_TOKEN": token} if token else None
        _run(["git", "push", "-u", "origin", branch], repo_path)
        result["pr_url"] = _run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                "Resolve schema drift in downstream code",
                "--body",
                _pr_body(before, after, result["diff"]),
            ],
            repo_path,
            env=gh_env,
        )
    _record(repo_name, final, latency_ms, result)
    return result


def _record(target: str, final: dict, latency_ms: int, result: dict) -> None:
    """Persist this run to the online-eval store (real production runs; no gold → recall=None)."""
    provider, model = provider_and_model()
    record_run(
        {
            "target": target,
            "provider": provider,
            "model": model,
            "healed": int(result["healed"]),
            "iterations": final.get("iteration", 0),
            "latency_ms": latency_ms,
            "input_tokens": final.get("input_tokens", 0),
            "output_tokens": final.get("output_tokens", 0),
            "context_recall": None,
            "pr_url": result["pr_url"],
        }
    )


def _pr_body(before: dict, after: dict, diff: str) -> str:
    delta = diff_openapi(before, after)
    changes = (
        "\n".join(f"- `{c.kind.value}` at `{c.location}`" for c in delta.changes) or "- (none)"
    )
    return (
        "## Schema drift resolved automatically\n\n"
        "An upstream OpenAPI change left downstream code stale. NexusRefactor located the impacted "
        "call sites, patched them, and verified the fix.\n\n"
        f"### Detected change(s)\n{changes}\n\n"
        "### Acceptance gate\n- ✅ mypy clean\n- ✅ pytest passing\n\n"
        f"### Patch\n```diff\n{diff}\n```\n\n"
        "🤖 Generated by NexusRefactor — gated by mypy + pytest exit codes."
    )
