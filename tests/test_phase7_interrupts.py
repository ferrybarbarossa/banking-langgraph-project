import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from src.graph import build_graph, make_initial_state, thread_config
from src.nodes import retrieval, semantic_retrieval


class FakeEmbeddingModel:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeEdgarClient:
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
          <p>Apple faces supply chain and platform concentration risks.</p>
          <h1>Item 1B. Unresolved Staff Comments</h1>
        </body></html>
        """


def test_graph_interrupts_for_human_review_and_resumes_with_approval(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(retrieval, "EdgarClient", FakeEdgarClient)
    monkeypatch.setattr(semantic_retrieval, "SentenceTransformerEmbeddingModel", FakeEmbeddingModel)
    connection = sqlite3.connect(tmp_path / "checkpoints.sqlite", check_same_thread=False)
    graph = build_graph(SqliteSaver(connection))
    config = thread_config("phase-7-human-review-test")

    interrupted = graph.invoke(make_initial_state("Should I buy Apple stock?"), config=config)

    assert "__interrupt__" in interrupted
    interrupt_payload = interrupted["__interrupt__"][0].value
    assert interrupt_payload["triggered_rules"] == ["C-001"]
    assert "draft_answer" in interrupt_payload

    resumed = graph.invoke(Command(resume={"decision": "approve"}), config=config)

    assert resumed["human_decision"] == "approve"
    assert resumed["final_answer"] == resumed["draft_answer"]
    assert resumed["audit_log"][-1]["node"] == "human_review"
