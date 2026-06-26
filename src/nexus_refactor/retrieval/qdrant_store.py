"""Qdrant wrapper: one collection holding BOTH a dense and a sparse (BM25) vector per chunk.

The client connection (`get_client`) is implemented — that API is stable. The collection
setup, indexing, and hybrid query are STUBS with guidance: wiring named dense + sparse vectors
and fusing them is exactly the Phase 1b learning, and the Qdrant API moves fast enough that you
should read the current docs rather than trust a frozen snippet here.

Docs to keep open while you implement:
  - Hybrid queries / Query API:  https://qdrant.tech/documentation/concepts/hybrid-queries/
  - fastembed integration:       https://qdrant.tech/documentation/fastembed/
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from nexus_refactor.config import get_settings

COLLECTION = "code_chunks"


@dataclass
class Chunk:
    """One indexed unit of code (function/class/region). Payload + text to embed."""

    chunk_id: str
    path: str
    symbol: str
    text: str
    repo: str  # for payload filtering — restrict search to one service/repo


def get_client() -> QdrantClient:
    """Connect to Qdrant (local docker by default; see .env QDRANT_URL)."""
    s = get_settings()
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)


def _dense_dim(model_name: str) -> int:
    """Dense vector size must equal the embedding model's output dim — probe it once rather than
    hardcode a magic number that silently breaks if you swap models."""
    return len(next(iter(TextEmbedding(model_name).embed(["probe"]))))


def ensure_collection(client: QdrantClient) -> None:
    """Create the collection with NAMED dense + sparse vectors, if absent.

    Dense and sparse are configured through DIFFERENT params because they're different objects:
      - dense  -> vectors_config: a fixed-length float array, compared by COSINE distance.
      - sparse -> sparse_vectors_config: an (index -> weight) map; no size/distance. modifier=IDF
                  makes Qdrant apply inverse-document-frequency server-side, which BM25 needs.
    The vector names ("dense"/"sparse") must match index_chunks and hybrid_search exactly.
    """
    s = get_settings()
    if client.collection_exists(COLLECTION):  # idempotent — that's what "ensure" means
        return
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": VectorParams(size=_dense_dim(s.dense_embed_model), distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(modifier=Modifier.IDF),
        },
    )
    # make payload filtering by repo fast
    client.create_payload_index(
        COLLECTION, field_name="repo", field_schema=PayloadSchemaType.KEYWORD
    )


def index_chunks(client: QdrantClient, chunks: list[Chunk]) -> None:
    """Embed (dense + sparse) and upsert chunks. Called by scripts/index_repo.py.

    Assumes the collection already exists (ensure_collection runs first). Embeds all chunk texts
    in one batch per model, then upserts one point per chunk carrying both named vectors.
    """
    if not chunks:
        return

    s = get_settings()
    dense = TextEmbedding(s.dense_embed_model)
    sparse = SparseTextEmbedding(s.sparse_embed_model)

    texts = [c.text for c in chunks]
    dense_vecs = dense.embed(texts)  # lazy generators, one vector per text
    sparse_vecs = sparse.embed(texts)

    points = [
        PointStruct(
            # Qdrant ids must be int/UUID, so derive a deterministic UUID from chunk_id —
            # re-indexing the same chunk then overwrites instead of duplicating. The readable
            # chunk_id stays in the payload.
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.chunk_id)),
            vector={
                "dense": dense_vec.tolist(),
                "sparse": SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
            },
            payload={
                "chunk_id": c.chunk_id,
                "path": c.path,
                "symbol": c.symbol,
                "repo": c.repo,
                "text": c.text,
            },
        )
        for c, dense_vec, sparse_vec in zip(chunks, dense_vecs, sparse_vecs, strict=True)
    ]
    client.upsert(collection_name=COLLECTION, points=points)


def hybrid_search(
    client: QdrantClient,
    query: str,
    *,
    repo: str | None = None,
    limit: int = 10,
) -> list[tuple[str, float]]:
    """Hybrid retrieval with Qdrant's server-side RRF fusion.

    One round-trip: two prefetch branches (dense + sparse) are fused by the server with
    Reciprocal Rank Fusion. retrieval/fusion.py is our studied/tested reference for the same
    algorithm. Applies the `repo` payload filter when provided.

    Returns (chunk_id, score) sorted best-first.
    """
    s = get_settings()
    dense = TextEmbedding(s.dense_embed_model)
    sparse = SparseTextEmbedding(s.sparse_embed_model)
    dense_q = next(iter(dense.embed([query])))  # embed wants a list; take the one vector
    sparse_q = next(iter(sparse.embed([query])))

    flt = Filter(must=[FieldCondition(key="repo", match=MatchValue(value=repo))]) if repo else None

    res = client.query_points(
        COLLECTION,
        prefetch=[
            Prefetch(query=dense_q.tolist(), using="dense", limit=limit, filter=flt),
            Prefetch(
                query=SparseVector(
                    indices=sparse_q.indices.tolist(), values=sparse_q.values.tolist()
                ),
                using="sparse",
                limit=limit,
                filter=flt,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),  # server fuses the two branches
        limit=limit,
        with_payload=["chunk_id"],
    )
    return [(str(h.payload["chunk_id"]), h.score) for h in res.points if h.payload]
