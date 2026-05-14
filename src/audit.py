from datetime import UTC, datetime

from src.state import AgentState, AuditEntry


def make_audit_entry(
    *,
    node: str,
    state: AgentState,
    notes: str = "",
) -> AuditEntry:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "node": node,
        "model": None,
        "input_tokens": None,
        "output_tokens": None,
        "retrieval_query": None,
        "metadata_filters": None,
        "retrieved_chunk_ids": None,
        "similarity_scores": None,
        "retrieval_rank_ordering": None,
        "compliance_rules_triggered": None,
        "human_decision": None,
        "revision_count": state["revision_count"],
        "notes": notes,
    }


def append_audit_entry(
    state: AgentState,
    *,
    node: str,
    notes: str = "",
) -> list[AuditEntry]:
    return [
        *state["audit_log"],
        make_audit_entry(node=node, state=state, notes=notes),
    ]
