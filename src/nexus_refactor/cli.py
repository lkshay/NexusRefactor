"""Command-line entry point. `nexus run <scenario_dir>` (or `make run SCENARIO=...`).

Implemented so you get a working feedback loop immediately. As you flesh out the nodes,
the same command shows real behavior — no CLI changes needed.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

import typer
import yaml
from langchain_core.tracers.context import collect_runs
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nexus_refactor.config import get_settings, setup_tracing, trace_url
from nexus_refactor.graph import build_graph
from nexus_refactor.metrics_store import provider_and_model, record_run, summarize
from nexus_refactor.resolve import resolve_drift

app = typer.Typer(add_completion=False, help="NexusRefactor — schema-drift refactor agent.")
console = Console()


def _recall(found: list[str], gold: list[str] | None) -> float | None:
    """Fraction of gold sites the agent surfaced (filename-level; scenarios have unique names)."""
    if not gold:
        return None
    g = {Path(p).name for p in gold}
    return round(len({Path(p).name for p in found} & g) / len(g), 3)


@app.command()
def run(scenario: str = typer.Argument(..., help="Path to a scenario dir (see eval/golden/).")):
    """Run the agent on one schema-drift scenario."""
    settings = get_settings()
    setup_tracing(settings)

    sdir = Path(scenario)
    if not sdir.is_dir():
        console.print(f"[red]No such scenario dir:[/red] {sdir}")
        raise typer.Exit(1)

    meta = yaml.safe_load((sdir / "scenario.yaml").read_text())
    before = yaml.safe_load((sdir / "openapi_before.yaml").read_text())
    after = yaml.safe_load((sdir / "openapi_after.yaml").read_text())

    console.print(
        Panel.fit(f"[bold]{meta.get('name', sdir.name)}[/bold]\n{meta.get('description', '')}")
    )

    # Work on a throwaway copy so the agent never mutates the golden fixture (and so verify's
    # mypy/pytest run isolated, outside this project's tree).
    work_dir = Path(tempfile.mkdtemp(prefix="nexus-run-"))
    shutil.copytree(sdir / "code", work_dir / "code")

    initial: dict = {
        "scenario_dir": str(sdir),
        "target_repo": str(work_dir / "code"),  # the working copy, not the fixture
        "repo_name": meta.get("repo"),  # logical repo for Qdrant filtering (None -> no filter)
        "openapi_before": before,
        "openapi_after": after,
        "iteration": 0,
        "max_iterations": settings.max_iterations,
        "history": [],
    }

    start = time.perf_counter()
    # collect_runs captures the LangGraph run tree so we can surface its LangSmith trace URL below.
    with collect_runs() as traced:
        try:
            final = build_graph().invoke(initial)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
    latency_ms = int((time.perf_counter() - start) * 1000)

    table = Table(title="Run trace", show_header=True, header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("event")
    for i, line in enumerate(final.get("history", []), 1):
        table.add_row(str(i), line)
    console.print(table)

    patch = final.get("current_patch", "")
    if patch:
        console.print(Panel(patch, title="current_patch", border_style="cyan"))

    clean = final.get("build_clean", False)
    verdict = "[green]CLEAN BUILD[/green]" if clean else "[red]NOT CLEAN[/red]"
    console.print(
        f"\nResult: {verdict}  "
        f"(iterations={final.get('iteration', 0)}/{final.get('max_iterations')})"
    )

    provider, model = provider_and_model()
    recall = _recall([s["path"] for s in final.get("candidate_sites", [])], meta.get("gold_sites"))
    record_run(
        {
            "target": meta.get("name", sdir.name),
            "provider": provider,
            "model": model,
            "healed": int(clean),
            "iterations": final.get("iteration", 0),
            "latency_ms": latency_ms,
            "input_tokens": final.get("input_tokens", 0),
            "output_tokens": final.get("output_tokens", 0),
            "context_recall": recall,
            "pr_url": None,
        }
    )
    console.print(f"[dim]recorded: {latency_ms} ms, recall={recall} → see `nexus metrics`[/dim]")

    url = trace_url(traced)
    if url:
        console.print(f"[blue]🔍 LangSmith trace:[/blue] {url}")


@app.command()
def show_graph():
    """Print the compiled graph as Mermaid (paste into a Markdown viewer to see it)."""
    graph = build_graph()
    console.print(graph.get_graph().draw_mermaid())


@app.command()
def metrics():
    """Online eval: summarize every recorded run (heal rate, latency, cost, recall)."""
    summary = summarize()
    if not summary.get("runs"):
        console.print(
            "[yellow]No runs recorded yet — run a scenario or `nexus resolve` first.[/yellow]"
        )
        return
    table = Table(title="Online eval — recorded runs", show_header=True, header_style="bold")
    table.add_column("metric")
    table.add_column("value", justify="right")
    for key, value in summary.items():
        table.add_row(key, str(value))
    console.print(table)


@app.command()
def resolve(
    repo: str = typer.Argument(..., help="Path to the target git repo whose spec changed."),
    spec: str = typer.Option("openapi.yaml", help="OpenAPI spec path within the repo."),
    code_dir: str = typer.Option("service", help="Consuming-code dir within the repo."),
    base: str = typer.Option("HEAD~1", help="Git ref of the spec's PREVIOUS version."),
    branch: str = typer.Option("nexus/schema-drift-fix", help="Fix branch to create."),
    open_pr: bool = typer.Option(
        True, "--open-pr/--no-open-pr", help="Open a PR via gh if healed."
    ),
):
    """Resolve schema drift in a git repo: fix the code on a branch, open a PR if it heals."""
    setup_tracing(get_settings())
    result = resolve_drift(repo, spec, code_dir, base, branch, open_pr)
    for line in result["history"]:
        console.print("  " + line)
    if not result["healed"]:
        console.print("[red]Could not heal the drift within budget — no PR opened.[/red]")
        raise typer.Exit(1)
    if result["pr_url"]:
        console.print(f"\n[green]✓ Opened PR:[/green] {result['pr_url']}")
    else:
        console.print("\n[green]✓ Healed[/green] (use --no-open-pr to skip the PR)")


if __name__ == "__main__":
    app()
