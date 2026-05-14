from datetime import UTC, datetime

from src.state import AgentState, AuditEntry


def make_audit_entry(
    *,
    node: str,
    state: AgentState,
    notes: str = "",
    retrieval_query: str | None = None,
    metadata_filters: dict | None = None,
    retrieved_chunk_ids: list[str] | None = None,
    similarity_scores: list[float] | None = None,
    retrieval_rank_ordering: list[int] | None = None,
    compliance_rules_triggered: list[str] | None = None,
    human_decision: str | None = None,
) -> AuditEntry:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "node": node,
        "model": None,
        "input_tokens": None,
        "output_tokens": None,
        "retrieval_query": retrieval_query,
        "metadata_filters": metadata_filters,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "similarity_scores": similarity_scores,
        "retrieval_rank_ordering": retrieval_rank_ordering,
        "compliance_rules_triggered": compliance_rules_triggered,
        "human_decision": human_decision,
        "revision_count": state["revision_count"],
        "notes": notes,
    }


def append_audit_entry(
    state: AgentState,
    *,
    node: str,
    notes: str = "",
    retrieval_query: str | None = None,
    metadata_filters: dict | None = None,
    retrieved_chunk_ids: list[str] | None = None,
    similarity_scores: list[float] | None = None,
    retrieval_rank_ordering: list[int] | None = None,
    compliance_rules_triggered: list[str] | None = None,
    human_decision: str | None = None,
) -> list[AuditEntry]:
    return [
        *state["audit_log"],
        make_audit_entry(
            node=node,
            state=state,
            notes=notes,
            retrieval_query=retrieval_query,
            metadata_filters=metadata_filters,
            retrieved_chunk_ids=retrieved_chunk_ids,
            similarity_scores=similarity_scores,
            retrieval_rank_ordering=retrieval_rank_ordering,
            compliance_rules_triggered=compliance_rules_triggered,
            human_decision=human_decision,
        ),
    ]
