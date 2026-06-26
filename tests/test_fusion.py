"""Regression tests for Reciprocal Rank Fusion (retrieval/fusion.py)."""

from __future__ import annotations

from nexus_refactor.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_ranks_consensus_first() -> None:
    list1 = ["a", "b", "c"]  # dense retriever
    list2 = ["a", "c", "d"]  # bm25 retriever
    fused = reciprocal_rank_fusion([list1, list2], k=60)
    ids = [doc for doc, _ in fused]

    assert ids[0] == "a"  # top of both lists -> clear winner
    assert set(ids) == {"a", "b", "c", "d"}  # a doc missing from one list still appears


def test_rrf_scores_descending_and_exact() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["a", "b"]], k=60)
    scores = [s for _, s in fused]

    assert scores == sorted(scores, reverse=True)
    # 'a' is rank 1 in both lists: 1/(60+1) + 1/(60+1)
    assert abs(fused[0][1] - 2 * (1 / 61)) < 1e-9
