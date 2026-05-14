from __future__ import annotations

from src.audit import append_audit_entry
from src.retrieval.embeddings import EmbeddingModel, SentenceTransformerEmbeddingModel
from src.retrieval.vector_store import rank_chunks_with_chroma
from src.state import AgentState, FilingChunk, RetrievalPlan, ScoredChunk
from src.tools.chunker import chunk_filing_sections

DEFAULT_TOP_K = 5


def semantic_retrieval_node(state: AgentState) -> dict[str, object]:
    top_k_chunks = retrieve_top_k_chunks(
        query=state["user_query"],
        plan=state["plan"],
        retrieved_chunks=state["retrieved_chunks"],
    )

    return {
        "top_k_chunks": top_k_chunks,
        "audit_log": append_audit_entry(
            state,
            node="semantic_retrieval",
            notes=f"Selected {len(top_k_chunks)} top-k semantic chunk(s).",
            retrieval_query=state["user_query"],
            metadata_filters=_metadata_filters(state["plan"]),
            retrieved_chunk_ids=[scored["chunk"]["chunk_id"] for scored in top_k_chunks],
            similarity_scores=[scored["similarity_score"] for scored in top_k_chunks],
            retrieval_rank_ordering=[scored["retrieval_rank"] for scored in top_k_chunks],
        ),
    }


def retrieve_top_k_chunks(
    *,
    query: str,
    plan: RetrievalPlan | None,
    retrieved_chunks: list[FilingChunk],
    top_k: int = DEFAULT_TOP_K,
    embedding_model: EmbeddingModel | None = None,
) -> list[ScoredChunk]:
    if plan is None or not retrieved_chunks:
        return []

    candidate_chunks = filter_chunks_for_plan(retrieved_chunks, plan)
    split_chunks = chunk_filing_sections(candidate_chunks)
    if not split_chunks:
        return []

    embedder = embedding_model or SentenceTransformerEmbeddingModel()
    query_embedding = embedder.embed([query])[0]
    chunk_embeddings = embedder.embed([chunk["text"] for chunk in split_chunks])

    return rank_chunks_with_chroma(
        chunks=split_chunks,
        query_embedding=query_embedding,
        chunk_embeddings=chunk_embeddings,
        top_k=top_k,
    )


def filter_chunks_for_plan(chunks: list[FilingChunk], plan: RetrievalPlan) -> list[FilingChunk]:
    return [
        chunk
        for chunk in chunks
        if chunk["ticker"] == plan["ticker"]
        and chunk["filing_type"] == plan["filing_type"]
        and chunk["section"] in plan["sections"]
    ]


def _metadata_filters(plan: RetrievalPlan | None) -> dict[str, object] | None:
    if plan is None:
        return None

    return {
        "ticker": plan["ticker"],
        "filing_type": plan["filing_type"],
        "sections": plan["sections"],
    }
