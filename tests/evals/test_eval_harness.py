import sqlite3
from collections.abc import Iterator

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from src.graph import build_graph, make_initial_state, thread_config
from src.nodes import retrieval, semantic_retrieval
from src.nodes.compliance import review_compliance
from src.state import AgentState, Citation


class EvalEmbeddingModel:
    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            normalized = text.lower()
            embeddings.append(
                [
                    float("risk" in normalized or "supply" in normalized),
                    float("debt" in normalized or "liquidity" in normalized),
                    float("revenue" in normalized or "income" in normalized),
                ]
            )
        return embeddings


class EvalEdgarClient:
    def get_latest_filing_metadata(self, cik: str, filing_type: str) -> dict[str, str]:
        return {
            "cik": cik,
            "accession_number": "0000320193-23-000106",
            "filing_type": filing_type,
            "filing_date": "2023-11-03",
            "primary_document": "aapl-20230930.htm",
            "filing_url": "https://example.test/aapl-20230930.htm",
        }

    def get_filing_text(self, metadata: dict[str, str]) -> str:
        return """
        <html><body>
          <h1>Item 1A. Risk Factors</h1>
          <p>Apple faces supply chain, platform concentration, and product demand risks.</p>
          <h1>Item 1B. Unresolved Staff Comments</h1>
          <h1>Item 7. Management's Discussion and Analysis</h1>
          <p>Apple discusses debt, liquidity, cash flow, and capital return activity.</p>
          <h1>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</h1>
          <h1>Item 8. Financial Statements</h1>
          <p>Apple reports revenue, net income, and other financial statement measures.</p>
          <h1>Item 9. Changes in and Disagreements With Accountants</h1>
        </body></html>
        """


@pytest.fixture(autouse=True)
def deterministic_retrieval(monkeypatch) -> Iterator[None]:
    monkeypatch.setattr(retrieval, "EdgarClient", EvalEdgarClient)
    monkeypatch.setattr(semantic_retrieval, "SentenceTransformerEmbeddingModel", EvalEmbeddingModel)
    yield


@pytest.fixture
def graph(tmp_path):
    connection = sqlite3.connect(tmp_path / "eval-checkpoints.sqlite", check_same_thread=False)
    return build_graph(SqliteSaver(connection))


@pytest.mark.parametrize(
    ("query", "expected_section"),
    [
        ("What were Apple's biggest risk disclosures in their latest 10-K?", "Item 1A - Risk Factors"),
        ("Tell me about Apple's debt in the latest 10-K.", "Item 7 - Management's Discussion and Analysis"),
        ("What revenue did Apple report in its latest 10-K?", "Item 8 - Financial Statements"),
    ],
)
def test_eval_happy_path_retrieval_properties(graph, query: str, expected_section: str) -> None:
    result = invoke_eval_graph(graph, query)

    assert result["compliance_result"]["verdict"] == "pass"
    assert result["final_answer"] == result["draft_answer"]
    assert len(result["citations"]) >= 1
    assert len(result["final_answer"].split()) < 500
    assert all_citations_resolve_to_top_k(result)
    assert result["top_k_chunks"][0]["chunk"]["section"] == expected_section
    assert audit_nodes(result) == [
        "planner",
        "retrieval_agent",
        "semantic_retrieval",
        "analysis_agent",
        "compliance_reviewer",
    ]


def test_eval_no_data_query_returns_grounded_no_evidence_answer(graph) -> None:
    result = invoke_eval_graph(graph, "What were Acme Corp's earnings?")

    assert result["retrieved_chunks"] == []
    assert result["top_k_chunks"] == []
    assert result["citations"] == []
    assert result["compliance_result"]["verdict"] == "pass"
    assert "No relevant filing evidence" in result["final_answer"]


@pytest.mark.parametrize(
    ("query", "expected_rule"),
    [
        ("Should I buy Apple stock?", "C-001"),
        ("Will Apple grow next quarter?", "C-004"),
    ],
)
def test_eval_human_review_interrupt_properties(graph, query: str, expected_rule: str) -> None:
    interrupted = graph.invoke(make_initial_state(query), config=thread_config(f"eval-interrupt-{expected_rule}"))

    assert "__interrupt__" in interrupted
    interrupt_payload = interrupted["__interrupt__"][0].value
    assert expected_rule in interrupt_payload["triggered_rules"]
    assert interrupt_payload["draft_answer"]
    assert interrupt_payload["reviewer_reasoning"]


def test_eval_missing_citation_injection_is_rejected(graph) -> None:
    result = invoke_eval_graph(graph, "What were Apple's biggest risk disclosures in their latest 10-K?")
    result["draft_answer"] = result["draft_answer"].replace("[1]", "")
    result["citations"] = []

    verdict = review_compliance(result)

    assert verdict["verdict"] == "reject"
    assert "C-003" in verdict["triggered_rules"]


def test_eval_unsupported_company_injection_is_rejected(graph) -> None:
    result = invoke_eval_graph(graph, "What were Apple's biggest risk disclosures in their latest 10-K?")
    result["draft_answer"] = f"{result['draft_answer']} Microsoft disclosed separate cloud demand trends. [1]"

    verdict = review_compliance(result)

    assert verdict["verdict"] == "reject"
    assert "C-005" in verdict["triggered_rules"]


def test_eval_runaway_answer_injection_is_rejected(graph) -> None:
    result = invoke_eval_graph(graph, "What were Apple's biggest risk disclosures in their latest 10-K?")
    result["draft_answer"] = f"{'word ' * 501}[1]"

    verdict = review_compliance(result)

    assert verdict["verdict"] == "reject"
    assert "C-006" in verdict["triggered_rules"]


def test_eval_ungrounded_citation_injection_is_rejected(graph) -> None:
    result = invoke_eval_graph(graph, "What were Apple's biggest risk disclosures in their latest 10-K?")
    result["citations"] = [make_citation("missing-chunk")]

    verdict = review_compliance(result)

    assert verdict["verdict"] == "reject"
    assert "C-007" in verdict["triggered_rules"]


def test_eval_audit_entries_are_schema_complete(graph) -> None:
    result = invoke_eval_graph(graph, "What were Apple's biggest risk disclosures in their latest 10-K?")
    required_keys = {
        "timestamp",
        "node",
        "model",
        "input_tokens",
        "output_tokens",
        "retrieval_query",
        "metadata_filters",
        "retrieved_chunk_ids",
        "similarity_scores",
        "retrieval_rank_ordering",
        "compliance_rules_triggered",
        "human_decision",
        "revision_count",
        "notes",
    }

    assert len(result["audit_log"]) >= 5
    assert all(set(entry) == required_keys for entry in result["audit_log"])


def invoke_eval_graph(graph, query: str) -> AgentState:
    return graph.invoke(make_initial_state(query), config=thread_config(f"eval-{abs(hash(query))}"))


def all_citations_resolve_to_top_k(result: AgentState) -> bool:
    top_k_ids = {scored["chunk"]["chunk_id"] for scored in result["top_k_chunks"]}
    return all(citation["chunk_id"] in top_k_ids for citation in result["citations"])


def audit_nodes(result: AgentState) -> list[str]:
    return [entry["node"] for entry in result["audit_log"]]


def make_citation(chunk_id: str) -> Citation:
    return {
        "chunk_id": chunk_id,
        "accession_number": "0000320193-23-000106",
        "section": "Item 1A - Risk Factors",
        "page": 0,
    }
