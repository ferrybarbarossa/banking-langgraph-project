from src.graph import _compiled_graph, run_graph
from src.nodes import retrieval, semantic_retrieval


class FakeEmbeddingModel:
    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            normalized = text.lower()
            embeddings.append([1.0, 0.0] if "risk" in normalized or "supply chain" in normalized else [0.0, 1.0])
        return embeddings


class FakeEdgarClient:
    def get_latest_filing_metadata(self, cik: str, filing_type: str) -> dict[str, str]:
        assert cik == "0000320193"
        assert filing_type == "10-K"
        return {
            "cik": cik,
            "accession_number": "0000320193-23-000106",
            "filing_type": "10-K",
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


def test_phase_7_graph_returns_final_answer_after_compliance_pass(monkeypatch) -> None:
    monkeypatch.setattr(retrieval, "EdgarClient", FakeEdgarClient)
    monkeypatch.setattr(semantic_retrieval, "SentenceTransformerEmbeddingModel", FakeEmbeddingModel)
    _compiled_graph.cache_clear()

    result = run_graph("What were Apple's biggest risk disclosures in their latest 10-K?")

    assert result["plan"] == {
        "ticker": "AAPL",
        "filing_type": "10-K",
        "sections": ["Item 1A - Risk Factors"],
        "reasoning": "Mapped query to AAPL 10-K; selected structural sections: Item 1A - Risk Factors.",
    }
    assert len(result["retrieved_chunks"]) == 1
    assert result["retrieved_chunks"][0]["ticker"] == "AAPL"
    assert result["retrieved_chunks"][0]["section"] == "Item 1A - Risk Factors"
    assert "supply chain" in result["retrieved_chunks"][0]["text"]
    assert len(result["top_k_chunks"]) == 1
    assert result["top_k_chunks"][0]["retrieval_rank"] == 1
    assert result["draft_answer"] is not None
    assert "supply chain" in result["draft_answer"]
    assert "[1]" in result["draft_answer"]
    assert result["citations"] == [
        {
            "chunk_id": result["top_k_chunks"][0]["chunk"]["chunk_id"],
            "accession_number": "0000320193-23-000106",
            "section": "Item 1A - Risk Factors",
            "page": 0,
        }
    ]
    assert result["compliance_result"] == {
        "verdict": "pass",
        "triggered_rules": [],
        "reasoning": "Deterministic compliance checks passed.",
    }
    assert result["final_answer"] == result["draft_answer"]
    assert [entry["node"] for entry in result["audit_log"]] == [
        "planner",
        "retrieval_agent",
        "semantic_retrieval",
        "analysis_agent",
        "compliance_reviewer",
    ]
