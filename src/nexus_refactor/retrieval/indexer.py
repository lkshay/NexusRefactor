"""Chunk a downstream repo into indexable units (function/class granularity).

Feeds scripts/index_repo.py -> qdrant_store.index_chunks.

Chunking strategy matters a lot for code search. A naive fixed-size window splits functions in
half and tanks recall. Prefer *structural* chunking:

  - Parse each .py file with the stdlib `ast` module.
  - Emit one Chunk per top-level function and per class (optionally per method).
  - Keep the symbol name and a stable chunk_id (e.g. f"{path}::{qualname}") in the payload —
    you'll need them to report candidate sites and to score context recall in eval.

Keep it Python-only for Phase 1 (matches the target language). When you add another language,
add another chunker behind the same `chunk_repo` interface.
"""

from __future__ import annotations

import ast
from pathlib import Path

from nexus_refactor.retrieval.qdrant_store import Chunk


def chunk_repo(repo_path: str | Path, repo_name: str) -> list[Chunk]:
    """Walk `repo_path`, return one Chunk per function/class.

    Args:
        repo_path: directory of downstream code to index.
        repo_name: logical name stored in payload (for payload filtering).
    """
    # One Chunk per TOP-LEVEL function/class: iterate tree.body, not ast.walk, so methods and
    # nested defs don't become separate overlapping chunks (and ids can't collide). Include
    # AsyncFunctionDef so `async def` clients aren't dropped. ast.get_source_segment slices by the
    # node's real source span — lineno/end_lineno are LINE numbers, so indexing `source` (a string)
    # by them would grab characters, not lines.
    chunks: list[Chunk] = []
    root = Path(repo_path)
    for py_file in root.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                rel = py_file.relative_to(root)
                chunks.append(
                    Chunk(
                        chunk_id=f"{rel}::{node.name}",
                        path=str(rel),
                        symbol=node.name,
                        text=ast.get_source_segment(source, node) or "",
                        repo=repo_name,
                    )
                )
    return chunks
