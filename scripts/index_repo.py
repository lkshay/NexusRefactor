"""Index a downstream repo into Qdrant for hybrid search.

    uv run python scripts/index_repo.py eval/golden/example_rename_field/code --repo example
    # clean re-index (drop this repo's existing points first, so renamed/removed code can't orphan):
    uv run python scripts/index_repo.py eval/golden/example_rename_field/code --repo example --reset
"""

from __future__ import annotations

import argparse

from qdrant_client.models import FieldCondition, Filter, MatchValue

from nexus_refactor.retrieval.indexer import chunk_repo
from nexus_refactor.retrieval.qdrant_store import (
    COLLECTION,
    ensure_collection,
    get_client,
    index_chunks,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Index a repo into Qdrant.")
    ap.add_argument("repo_path", help="directory of downstream code to index")
    ap.add_argument("--repo", required=True, help="logical repo name (stored in payload)")
    ap.add_argument(
        "--reset",
        action="store_true",
        help="delete this repo's existing points before indexing (clean re-index)",
    )
    args = ap.parse_args()

    client = get_client()
    ensure_collection(client)

    if args.reset:
        client.delete(
            COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="repo", match=MatchValue(value=args.repo))]
            ),
        )
        print(f"reset: cleared existing points for repo={args.repo!r}")

    chunks = chunk_repo(args.repo_path, args.repo)
    index_chunks(client, chunks)
    print(f"Indexed {len(chunks)} chunks from {args.repo_path} as repo={args.repo!r}")


if __name__ == "__main__":
    main()
