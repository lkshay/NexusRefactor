"""The three Phase 1c metrics. Each scores ONE scenario; run_eval aggregates with bootstrapped CIs.

Definitions (also in docs/DECISIONS.md):
  - compilation_success: 1.0 if the agent reached build_clean, else 0.0.
  - context_recall:      fraction of the gold impacted sites that `search` surfaced.
  - patch_minimality:    FILE-level precision — of the files the agent edited, the fraction the
                         gold patch also edits (1.0 = no extraneous churn). Line-level distance is
                         a future refinement; file-level is simple and interpretable.

Paths are normalized (a leading "code/" stripped) so the scenario's "code/x.py" gold paths line
up with the agent's repo-relative "x.py".
"""

from __future__ import annotations

from nexus_refactor.state import RefactorState


def compilation_success(final_state: RefactorState) -> float:
    """Headline binary metric: did the agent reach a clean build?"""
    return 1.0 if final_state.get("build_clean") else 0.0


def context_recall(found_sites: list[str], gold_sites: list[str]) -> float:
    """recall = |found ∩ gold| / |gold|. 1.0 when there are no gold sites (nothing to find)."""
    gold = {_norm(p) for p in gold_sites}
    if not gold:
        return 1.0
    found = {_norm(p) for p in found_sites}
    return len(found & gold) / len(gold)


def patch_minimality(gold_patch: str, agent_patch: str) -> float:
    """File-level precision: of the files the agent changed, the fraction gold also changed.

    1.0 means no churn outside the files the minimal fix touches. An empty agent patch scores 1.0
    (no churn) — whether it actually fixed anything is what compilation_success measures.
    """
    agent_files = _changed_files(agent_patch)
    if not agent_files:
        return 1.0
    gold_files = _changed_files(gold_patch)
    return len(agent_files & gold_files) / len(agent_files)


def _norm(path: str) -> str:
    """Normalize so scenario gold paths and agent repo-relative paths compare equal."""
    return path.strip().removeprefix("./").removeprefix("code/")


def _changed_files(unified_diff: str) -> set[str]:
    """Files a unified diff modifies, from its `+++ b/<path>` headers."""
    files = set()
    for line in unified_diff.splitlines():
        if line.startswith("+++ "):
            files.add(_norm(line[4:].strip().removeprefix("b/")))
    return files
