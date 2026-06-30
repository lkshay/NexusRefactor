"""Online eval store — persist every agent run, summarize the fleet.

Phase 2's instrumentation: each run (CLI `run`, `resolve`, or the webhook job) records its outcome
here, so you can report heal rate / latency / cost / recall over REAL runs — the *online* half of
the eval, distinct from the curated golden-set eval (the *offline* half) in eval/.

SQLite by default (a file, no extra service); point NEXUS_METRICS_DB elsewhere — or swap this store
for Postgres — when you scale.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nexus_refactor.config import get_settings

DEFAULT_DB = os.environ.get("NEXUS_METRICS_DB", "nexus_metrics.db")

# Rough $ per 1M tokens (input, output). 0 for local models. Update as you measure real bills.
_RATES: dict[str, tuple[float, float]] = {
    "deepseek-v4-flash": (0.28, 0.42),
    "deepseek-v4-pro": (0.55, 2.19),
    "gpt-4o": (2.50, 10.0),
}

_COLUMNS = (
    "ts",
    "target",
    "provider",
    "model",
    "healed",
    "iterations",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "context_recall",
    "pr_url",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    target TEXT,
    provider TEXT,
    model TEXT,
    healed INTEGER,
    iterations INTEGER,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    context_recall REAL,
    pr_url TEXT
)
"""


def _connect(db: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.execute(_SCHEMA)
    return conn


def record_run(run: dict[str, Any], db: str | Path = DEFAULT_DB) -> None:
    """Persist one run's metrics. `run` keys are a subset of _COLUMNS (ts auto-filled)."""
    row = dict(run)
    row.setdefault("ts", datetime.now(UTC).isoformat(timespec="seconds"))
    placeholders = ", ".join("?" * len(_COLUMNS))
    with closing(_connect(db)) as conn:
        conn.execute(
            f"INSERT INTO runs ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
            tuple(row.get(col) for col in _COLUMNS),
        )
        conn.commit()


def provider_and_model() -> tuple[str, str]:
    """The provider name + model `choose_provider` will use (for the metrics row)."""
    s = get_settings()
    model = {
        "openai": s.openai_model,
        "anthropic": s.anthropic_model,
        "deepseek": s.deepseek_model,
        "ollama": s.ollama_model,
    }.get(s.llm_provider, "")
    return s.llm_provider, model


def _cost(model: str | None, inp: int, out: int) -> float:
    rate_in, rate_out = _RATES.get(model or "", (0.0, 0.0))
    return inp / 1e6 * rate_in + out / 1e6 * rate_out


def _percentile(sorted_vals: list[int], p: int) -> int | None:
    if not sorted_vals:
        return None
    return sorted_vals[min(len(sorted_vals) - 1, int(p / 100 * len(sorted_vals)))]


def summarize(db: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Aggregate all recorded runs into the online-eval headline metrics."""
    with closing(_connect(db)) as conn:
        rows = conn.execute(
            "SELECT healed, iterations, latency_ms, input_tokens, output_tokens, "
            "context_recall, pr_url, model FROM runs"
        ).fetchall()
    n = len(rows)
    if not n:
        return {"runs": 0}
    latencies = sorted(r[2] for r in rows if r[2] is not None)
    recalls = [r[5] for r in rows if r[5] is not None]
    return {
        "runs": n,
        "heal_rate": round(sum(r[0] or 0 for r in rows) / n, 3),
        "avg_iterations": round(sum(r[1] or 0 for r in rows) / n, 2),
        "latency_ms_p50": _percentile(latencies, 50),
        "latency_ms_p95": _percentile(latencies, 95),
        "total_tokens": sum((r[3] or 0) + (r[4] or 0) for r in rows),
        "est_cost_usd": round(sum(_cost(r[7], r[3] or 0, r[4] or 0) for r in rows), 4),
        "context_recall": round(sum(recalls) / len(recalls), 3) if recalls else None,
        "prs_opened": sum(1 for r in rows if r[6]),
    }
