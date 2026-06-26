"""Tests for the eval metrics — pure functions, no LLM or Qdrant needed."""

from __future__ import annotations

from eval.metrics import compilation_success, context_recall, patch_minimality


def test_compilation_success() -> None:
    assert compilation_success({"build_clean": True}) == 1.0
    assert compilation_success({"build_clean": False}) == 0.0
    assert compilation_success({}) == 0.0


def test_context_recall_normalizes_paths() -> None:
    # gold is "code/client.py"; search returns repo-relative "client.py" — must still match.
    assert context_recall(["client.py"], ["code/client.py"]) == 1.0


def test_context_recall_partial() -> None:
    assert context_recall(["a.py"], ["code/a.py", "code/b.py"]) == 0.5


def test_context_recall_noise_does_not_lower_recall() -> None:
    # extra found sites are a precision concern, not recall
    assert context_recall(["a.py", "b.py", "c.py"], ["code/a.py"]) == 1.0


def test_patch_minimality_only_gold_file() -> None:
    gold = "--- a/code/client.py\n+++ b/code/client.py\n@@ -1 +1 @@\n-x\n+y\n"
    agent = "--- a/client.py\n+++ b/client.py\n@@ -1 +1 @@\n-x\n+y\n"
    assert patch_minimality(gold, agent) == 1.0


def test_patch_minimality_penalizes_extra_file() -> None:
    gold = "+++ b/code/client.py\n"
    agent = "+++ b/client.py\n+++ b/models.py\n"  # touched an extra file
    assert patch_minimality(gold, agent) == 0.5


def test_patch_minimality_empty_agent_patch() -> None:
    assert patch_minimality("+++ b/code/client.py\n", "") == 1.0
