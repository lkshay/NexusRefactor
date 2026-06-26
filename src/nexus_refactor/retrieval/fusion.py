"""Reciprocal Rank Fusion (RRF) — combine multiple ranked result lists into one.

>>> STUB — IMPLEMENT IN PHASE 1b. This is your best "first algorithm" exercise. <<<
There are failing/xfail tests waiting in tests/test_fusion.py. Make them pass.

RRF is delightfully simple and parameter-light (that's why it's the default fusion in many
hybrid search stacks, including Qdrant's native fusion). For a document `d` appearing across
several ranked lists:

        RRF_score(d) = sum over each list L of   1 / (k + rank_L(d))

where `rank_L(d)` is d's 1-based position in list L (best = 1), and `k` is a smoothing
constant (60 is the conventional default). A document missing from a list contributes 0 for
that list. Higher score = better; return results sorted by score descending.

Why it works: 1/(k+rank) decays gently, so being ranked #1 in one retriever and absent in
another can still beat being #5 in both — but agreement across retrievers compounds. And
because it uses *ranks*, not raw scores, you don't have to normalize dense cosine distances
against BM25 term scores (which live on totally different scales). That scale-invariance is
the practical reason to reach for RRF over score-weighted fusion.

Implement `reciprocal_rank_fusion` to satisfy tests/test_fusion.py, then later compare your
result against Qdrant's built-in fusion to confirm you understand it.
"""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Fuse several ranked lists of document ids into one ranking.

    Args:
        ranked_lists: each inner list is doc ids ordered best-first (e.g. one from the
            dense retriever, one from BM25).
        k: RRF smoothing constant (default 60).

    Returns:
        (doc_id, fused_score) tuples sorted by fused_score descending. Ties: your call,
        but be deterministic (the tests assume stable behavior).
    """
    # Accumulate each doc's RRF score across every list. The outer list index is irrelevant —
    # all retrievers contribute symmetrically — so we don't enumerate it.
    fused_scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, doc_id in enumerate(lst, start=1):
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1 / (k + rank)

    # Return the fused scores sorted by score descending.
    return sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
