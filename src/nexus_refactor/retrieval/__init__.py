"""Hybrid code retrieval: dense (semantic) + sparse (BM25) over Qdrant, fused with RRF.

Why hybrid for *code*? Dense embeddings capture intent ("get the user's display name") but
miss exact tokens; BM25 nails exact identifiers/namespaces ("user_name", "UserService") but
misses paraphrase. Schema drift needs both: you're hunting an exact renamed identifier AND the
places that *use the concept* it represents. Fusing the two beats either alone.
"""
