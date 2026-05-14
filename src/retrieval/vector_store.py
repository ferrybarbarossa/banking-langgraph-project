from __future__ import annotations

import uuid
from typing import Any

import chromadb
from chromadb.config import Settings

from src.state import FilingChunk, ScoredChunk


def rank_chunks_with_chroma(
    *,
    chunks: list[FilingChunk],
    query_embedding: list[float],
    chunk_embeddings: list[list[float]],
    top_k: int,
) -> list[ScoredChunk]:
    if not chunks or not chunk_embeddings:
        return []

    collection_name = f"query_{uuid.uuid4().hex}"
    client = chromadb.Client(Settings(anonymized_telemetry=False, is_persistent=False))
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )

    collection.add(
        ids=[chunk["chunk_id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        embeddings=chunk_embeddings,
        metadatas=[_chunk_metadata(chunk) for chunk in chunks],
    )
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, len(chunks)),
        include=["distances"],
    )

    ranked_chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    result_ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    scored_chunks: list[ScoredChunk] = []
    for rank, (chunk_id, distance) in enumerate(zip(result_ids, distances, strict=True), start=1):
        scored_chunks.append(
            {
                "chunk": ranked_chunks_by_id[chunk_id],
                "similarity_score": 1.0 - float(distance),
                "retrieval_rank": rank,
            }
        )

    return scored_chunks


def _chunk_metadata(chunk: FilingChunk) -> dict[str, Any]:
    return {
        "ticker": chunk["ticker"],
        "accession_number": chunk["accession_number"],
        "filing_type": chunk["filing_type"],
        "filing_date": chunk["filing_date"],
        "section": chunk["section"],
        "page": chunk["page"],
    }
