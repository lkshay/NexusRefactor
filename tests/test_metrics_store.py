"""The online-eval store: record runs, summarize the fleet."""

from __future__ import annotations

from pathlib import Path

from nexus_refactor.metrics_store import record_run, summarize


def _run(**over: object) -> dict:
    base = {
        "target": "example",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "healed": 1,
        "iterations": 1,
        "latency_ms": 1000,
        "input_tokens": 1_000_000,  # 1M, so cost math is easy to assert
        "output_tokens": 1_000_000,
        "context_recall": 1.0,
        "pr_url": None,
    }
    base.update(over)
    return base


def test_empty_store_reports_zero_runs(tmp_path: Path) -> None:
    assert summarize(tmp_path / "m.db") == {"runs": 0}


def test_record_then_summarize(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    record_run(_run(healed=1, latency_ms=1000), db)
    record_run(_run(healed=0, latency_ms=3000, pr_url="http://pr/1"), db)

    s = summarize(db)
    assert s["runs"] == 2
    assert s["heal_rate"] == 0.5
    assert s["prs_opened"] == 1
    # p50/p95 over [1000, 3000] — both percentiles land on a real sample.
    assert s["latency_ms_p50"] in (1000, 3000)
    assert s["latency_ms_p95"] == 3000


def test_cost_uses_the_rate_table(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    # 1M in + 1M out at deepseek-v4-flash (0.28, 0.42) → 0.70 USD.
    record_run(_run(), db)
    assert summarize(db)["est_cost_usd"] == 0.70


def test_unknown_model_costs_zero(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    record_run(_run(model="mystery-model"), db)
    assert summarize(db)["est_cost_usd"] == 0.0


def test_recall_averages_only_present_values(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    record_run(_run(context_recall=1.0), db)
    record_run(_run(context_recall=None), db)  # a real `resolve` run has no gold
    assert summarize(db)["context_recall"] == 1.0
