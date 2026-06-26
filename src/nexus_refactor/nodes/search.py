"""search: SchemaDelta -> candidate call sites, via hybrid retrieval (Qdrant).

For each impactful change, query the OLD identifier (the broken downstream code still uses it),
run hybrid search, and de-duplicate the hits into a ranked CandidateSite list. Additive changes
(FIELD_ADDED) are skipped — they don't break existing callers, so there's nothing to find.

Honesty note for your eval: "context recall" (did search find ALL impacted sites?) is the
metric that lives or dies here. Measure it; don't assume it.
"""

from __future__ import annotations

from nexus_refactor.retrieval.qdrant_store import get_client, hybrid_search
from nexus_refactor.schema.delta import Change, ChangeKind
from nexus_refactor.state import CandidateSite, RefactorState


def _query_for_change(change: Change) -> str | None:
    """Retrieval query for one change, or None to skip it.

    Query the field's identifier — the leaf of `location` (e.g. `...User.user_name` -> "user_name")
    — since that's what stale downstream code references. We use `location`, not `change.before`,
    because for a type change `before` is the TYPE, not the field name. (Additive changes don't
    break existing callers, so skip them.)
    """
    if change.kind is ChangeKind.FIELD_ADDED:
        return None
    return change.location.rsplit(".", 1)[-1] or change.before


def search_node(state: RefactorState) -> dict:
    delta = state.get("schema_diff")
    if delta is None or delta.is_empty():
        return {"candidate_sites": [], "history": ["search: empty delta -> 0 sites"]}

    client = get_client()
    repo = state.get("repo_name")  # None -> no payload filter (fine for a single-repo collection)

    # De-dup across changes: the same chunk can surface for several changes; keep the best score.
    best: dict[str, CandidateSite] = {}
    for change in delta.changes:
        query = _query_for_change(change)
        if query is None:
            continue
        for chunk_id, score in hybrid_search(client, query, repo=repo, limit=5):
            if chunk_id not in best or score > best[chunk_id]["score"]:
                path, _, symbol = chunk_id.partition("::")  # chunk_id == "path::symbol"
                best[chunk_id] = {"path": path, "symbol": symbol, "score": score}

    sites = sorted(best.values(), key=lambda s: s["score"], reverse=True)
    return {
        "candidate_sites": sites,
        "history": [f"search: {len(sites)} site(s) from {len(delta.changes)} change(s)"],
    }
