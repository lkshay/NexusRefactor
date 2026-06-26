"""Evaluation harness. `make eval` / `python -m eval.run_eval`.

For each golden scenario: index its code into Qdrant, run the agent on a throwaway working copy,
and score compilation_success / context_recall / patch_minimality. Each metric is aggregated with
a bootstrapped 95% CI (see bootstrap.py). Be honest about N.

Note: each scenario invokes the LLM (refactor), so a full run is as slow as N agent runs.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rich.console import Console
from rich.table import Table

from eval import metrics
from eval.bootstrap import bootstrap_ci
from nexus_refactor.config import get_settings
from nexus_refactor.graph import build_graph
from nexus_refactor.retrieval.indexer import chunk_repo
from nexus_refactor.retrieval.qdrant_store import (
    COLLECTION,
    ensure_collection,
    get_client,
    index_chunks,
)

console = Console()
GOLDEN_DIR = Path(__file__).parent / "golden"


def discover_scenarios() -> list[Path]:
    """Every subdir of eval/golden/ that has a scenario.yaml is a scenario."""
    return sorted(p.parent for p in GOLDEN_DIR.glob("*/scenario.yaml"))


def _index_scenario(client: Any, code_dir: Path, repo_name: str) -> None:
    """Clean re-index of one scenario's code under its repo name (so search can find it)."""
    ensure_collection(client)
    client.delete(
        COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="repo", match=MatchValue(value=repo_name))]
        ),
    )
    index_chunks(client, chunk_repo(code_dir, repo_name))


def _run_scenario(sdir: Path, graph: Any, client: Any) -> dict[str, Any]:
    meta = yaml.safe_load((sdir / "scenario.yaml").read_text())
    repo_name = meta.get("repo") or sdir.name
    _index_scenario(client, sdir / "code", repo_name)

    work = Path(tempfile.mkdtemp(prefix="nexus-eval-"))
    shutil.copytree(sdir / "code", work / "code")
    try:
        final = graph.invoke(
            {
                "scenario_dir": str(sdir),
                "target_repo": str(work / "code"),
                "repo_name": repo_name,
                "openapi_before": yaml.safe_load((sdir / "openapi_before.yaml").read_text()),
                "openapi_after": yaml.safe_load((sdir / "openapi_after.yaml").read_text()),
                "iteration": 0,
                "max_iterations": get_settings().max_iterations,
                "history": [],
            }
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)

    gold_file = sdir / "gold_patch.diff"
    gold_patch = gold_file.read_text() if gold_file.exists() else ""
    found = [s["path"] for s in final.get("candidate_sites", [])]
    return {
        "name": meta.get("name", sdir.name),
        "compile": metrics.compilation_success(final),
        "recall": metrics.context_recall(found, meta.get("gold_sites", [])),
        "minimality": metrics.patch_minimality(gold_patch, final.get("current_patch", "")),
    }


def report(name: str, scores: list[float]) -> None:
    """Print one metric with its bootstrapped 95% CI and honest N."""
    point, lo, hi = bootstrap_ci(scores)
    console.print(
        f"[bold]{name}[/bold]: {point:.3f}  95% CI [{lo:.3f}, {hi:.3f}]  (N={len(scores)})"
    )


def main() -> None:
    scenarios = discover_scenarios()
    console.print(f"Running {len(scenarios)} scenario(s) — each invokes the LLM, so this is slow…")
    graph = build_graph()
    client = get_client()
    results = [_run_scenario(s, graph, client) for s in scenarios]

    table = Table(title="Per-scenario")
    for col in ("scenario", "compile", "recall", "minimality"):
        table.add_column(col)
    for r in results:
        table.add_row(
            r["name"], f"{r['compile']:.0f}", f"{r['recall']:.2f}", f"{r['minimality']:.2f}"
        )
    console.print(table)

    report("compilation_success", [r["compile"] for r in results])
    report("context_recall", [r["recall"] for r in results])
    report("patch_minimality", [r["minimality"] for r in results])


if __name__ == "__main__":
    main()
