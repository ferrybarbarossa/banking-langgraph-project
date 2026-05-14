from src.graph import _compiled_graph, run_graph
from src.nodes import retrieval


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


def test_phase_3_graph_plans_and_retrieves_structural_chunks(monkeypatch) -> None:
    monkeypatch.setattr(retrieval, "EdgarClient", FakeEdgarClient)
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
    assert [entry["node"] for entry in result["audit_log"]] == ["planner", "retrieval_agent"]
