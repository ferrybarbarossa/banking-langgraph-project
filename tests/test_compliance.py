from src.nodes.compliance import review_compliance
from src.state import AgentState, Citation, FilingChunk, ScoredChunk


def test_compliance_passes_grounded_cited_answer() -> None:
    state = make_state(
        draft_answer="Apple disclosed supply chain risks in its filing. [1]",
        citations=[make_citation("chunk-1")],
    )

    assert review_compliance(state) == {
        "verdict": "pass",
        "triggered_rules": [],
        "reasoning": "Deterministic compliance checks passed.",
    }


def test_compliance_flags_investment_advice_for_human_review() -> None:
    state = make_state(
        user_query="Should I buy Apple stock?",
        draft_answer="Apple disclosed supply chain risks. [1]",
        citations=[make_citation("chunk-1")],
    )

    verdict = review_compliance(state)

    assert verdict["verdict"] == "flag_for_human"
    assert verdict["triggered_rules"] == ["C-001"]


def test_compliance_rejects_missing_citations() -> None:
    state = make_state(draft_answer="Apple disclosed supply chain risks.", citations=[])

    verdict = review_compliance(state)

    assert verdict["verdict"] == "reject"
    assert verdict["triggered_rules"] == ["C-003"]


def test_compliance_flags_forward_looking_language() -> None:
    state = make_state(
        user_query="Will Apple grow next quarter?",
        draft_answer="Apple disclosed supply chain risks. [1]",
        citations=[make_citation("chunk-1")],
    )

    verdict = review_compliance(state)

    assert verdict["verdict"] == "flag_for_human"
    assert verdict["triggered_rules"] == ["C-004"]


def test_compliance_rejects_unsupported_company_references() -> None:
    state = make_state(
        draft_answer="Apple disclosed supply chain risks, while Microsoft discussed cloud demand. [1]",
        citations=[make_citation("chunk-1")],
    )

    verdict = review_compliance(state)

    assert verdict["verdict"] == "reject"
    assert verdict["triggered_rules"] == ["C-005"]


def test_compliance_rejects_runaway_length() -> None:
    state = make_state(
        draft_answer=f"{'word ' * 501}[1]",
        citations=[make_citation("chunk-1")],
    )

    verdict = review_compliance(state)

    assert verdict["verdict"] == "reject"
    assert verdict["triggered_rules"] == ["C-006"]


def test_compliance_rejects_ungrounded_citations() -> None:
    state = make_state(
        draft_answer="Apple disclosed supply chain risks. [1]",
        citations=[make_citation("missing-chunk")],
    )

    verdict = review_compliance(state)

    assert verdict["verdict"] == "reject"
    assert verdict["triggered_rules"] == ["C-007"]


def make_state(
    *,
    user_query: str = "What are Apple's risks?",
    draft_answer: str,
    citations: list[Citation],
) -> AgentState:
    return {
        "user_query": user_query,
        "plan": {
            "ticker": "AAPL",
            "filing_type": "10-K",
            "sections": ["Item 1A - Risk Factors"],
            "reasoning": "test",
        },
        "retrieved_chunks": [],
        "top_k_chunks": [make_scored_chunk("chunk-1")],
        "draft_answer": draft_answer,
        "citations": citations,
        "compliance_result": None,
        "human_decision": None,
        "human_feedback": None,
        "revision_count": 0,
        "final_answer": None,
        "audit_log": [],
    }


def make_scored_chunk(chunk_id: str) -> ScoredChunk:
    chunk: FilingChunk = {
        "chunk_id": chunk_id,
        "ticker": "AAPL",
        "accession_number": "0000320193-23-000106",
        "filing_type": "10-K",
        "filing_date": "2023-11-03",
        "section": "Item 1A - Risk Factors",
        "text": "Apple disclosed supply chain risks.",
        "page": 0,
    }
    return {"chunk": chunk, "similarity_score": 1.0, "retrieval_rank": 1}


def make_citation(chunk_id: str) -> Citation:
    return {
        "chunk_id": chunk_id,
        "accession_number": "0000320193-23-000106",
        "section": "Item 1A - Risk Factors",
        "page": 0,
    }
