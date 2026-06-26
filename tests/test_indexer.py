"""Tests for the ast-based repo chunker."""

from __future__ import annotations

from pathlib import Path

from nexus_refactor.retrieval.indexer import chunk_repo

CODE = Path(__file__).resolve().parents[1] / "eval" / "golden" / "example_rename_field" / "code"


def test_chunks_top_level_symbols() -> None:
    symbols = {c.symbol for c in chunk_repo(CODE, "example")}
    # the top-level function, class, and test in the example fixture
    assert {"get_display_name", "User", "test_get_display_name"} <= symbols


def test_chunk_text_is_real_source_not_char_slice() -> None:
    chunks = chunk_repo(CODE, "example")
    fn = next(c for c in chunks if c.symbol == "get_display_name")

    # text must be the actual function source (the line-vs-char bug would make this fail)
    assert fn.text.startswith("def get_display_name(")
    assert "user.user_name" in fn.text
    assert fn.path == "client.py"
    assert fn.chunk_id == "client.py::get_display_name"
    assert fn.repo == "example"
