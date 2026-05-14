from __future__ import annotations

import re

from src.audit import append_audit_entry
from src.state import AgentState, Citation, ScoredChunk

MAX_EVIDENCE_SNIPPET_CHARS = 260
MAX_DRAFT_WORDS = 500


def analysis_agent_node(state: AgentState) -> dict[str, object]:
    draft_answer, citations = synthesize_cited_answer(state["user_query"], state["top_k_chunks"])
    return {
        "draft_answer": draft_answer,
        "citations": citations,
        "audit_log": append_audit_entry(
            state,
            node="analysis_agent",
            notes=f"Generated cited draft answer from {len(state['top_k_chunks'])} top-k chunk(s).",
            retrieval_query=state["user_query"],
            retrieved_chunk_ids=[citation["chunk_id"] for citation in citations],
        ),
    }


def synthesize_cited_answer(query: str, top_k_chunks: list[ScoredChunk]) -> tuple[str, list[Citation]]:
    if not top_k_chunks:
        return (
            "No relevant filing evidence was found for this query, so no grounded answer can be drafted.",
            [],
        )

    citations = [_citation_from_scored_chunk(scored_chunk) for scored_chunk in top_k_chunks]
    lead_chunk = top_k_chunks[0]["chunk"]
    filing_label = f"{lead_chunk['ticker']} {lead_chunk['filing_type']} filed {lead_chunk['filing_date']}"

    evidence_lines = []
    for index, scored_chunk in enumerate(top_k_chunks, start=1):
        chunk = scored_chunk["chunk"]
        citation_marker = format_citation_marker(index)
        snippet = evidence_snippet(chunk["text"])
        evidence_lines.append(f"- {snippet} {citation_marker}")

    answer = (
        f"Based on the retrieved {filing_label} evidence, the draft answer to \"{query}\" is:\n\n"
        + "\n".join(evidence_lines)
    )
    return truncate_words(answer, MAX_DRAFT_WORDS), citations


def _citation_from_scored_chunk(scored_chunk: ScoredChunk) -> Citation:
    chunk = scored_chunk["chunk"]
    return {
        "chunk_id": chunk["chunk_id"],
        "accession_number": chunk["accession_number"],
        "section": chunk["section"],
        "page": chunk["page"],
    }


def format_citation_marker(index: int) -> str:
    return f"[{index}]"


def evidence_snippet(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= MAX_EVIDENCE_SNIPPET_CHARS:
        return normalized

    truncated = normalized[:MAX_EVIDENCE_SNIPPET_CHARS].rsplit(" ", maxsplit=1)[0]
    return f"{truncated}..."


def truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text

    return " ".join(words[:max_words])
