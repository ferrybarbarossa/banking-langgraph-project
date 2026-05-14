from src.nodes.semantic_retrieval import filter_chunks_for_plan, retrieve_top_k_chunks
from src.state import FilingChunk, RetrievalPlan
from src.tools.chunker import chunk_filing_sections


class KeywordEmbeddingModel:
    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            normalized = text.lower()
            if "supply chain" in normalized:
                embeddings.append([1.0, 0.0, 0.0])
            elif "platform" in normalized:
                embeddings.append([0.8, 0.2, 0.0])
            else:
                embeddings.append([0.0, 1.0, 0.0])
        return embeddings


def test_chunk_filing_sections_preserves_traceability_metadata() -> None:
    source_chunk = make_chunk(
        chunk_id="AAPL:0001:item-1a-risk-factors:1",
        section="Item 1A - Risk Factors",
        text="Alpha sentence. Beta sentence. Gamma sentence.",
    )

    chunks = chunk_filing_sections([source_chunk], chunk_size=20, chunk_overlap=0)

    assert len(chunks) > 1
    assert chunks[0]["chunk_id"] == "AAPL:0001:item-1a-risk-factors:1:part-1"
    assert chunks[0]["ticker"] == "AAPL"
    assert chunks[0]["accession_number"] == "0000320193-23-000106"


def test_filter_chunks_for_plan_applies_metadata_before_ranking() -> None:
    plan = make_plan()
    matching_chunk = make_chunk("match", "Item 1A - Risk Factors", "matching risk text")
    wrong_section_chunk = make_chunk("wrong-section", "Item 8 - Financial Statements", "matching risk text")

    assert filter_chunks_for_plan([matching_chunk, wrong_section_chunk], plan) == [matching_chunk]


def test_retrieve_top_k_chunks_ranks_semantic_matches() -> None:
    plan = make_plan()
    chunks = [
        make_chunk("risk-supply", "Item 1A - Risk Factors", "Supply chain risks can disrupt production."),
        make_chunk("risk-platform", "Item 1A - Risk Factors", "Platform concentration creates business risk."),
        make_chunk("risk-other", "Item 1A - Risk Factors", "Unrelated litigation disclosure."),
    ]

    top_k_chunks = retrieve_top_k_chunks(
        query="supply chain risk",
        plan=plan,
        retrieved_chunks=chunks,
        top_k=2,
        embedding_model=KeywordEmbeddingModel(),
    )

    assert [scored["chunk"]["chunk_id"] for scored in top_k_chunks] == ["risk-supply:part-1", "risk-platform:part-1"]
    assert [scored["retrieval_rank"] for scored in top_k_chunks] == [1, 2]
    assert top_k_chunks[0]["similarity_score"] >= top_k_chunks[1]["similarity_score"]


def make_plan() -> RetrievalPlan:
    return {
        "ticker": "AAPL",
        "filing_type": "10-K",
        "sections": ["Item 1A - Risk Factors"],
        "reasoning": "test plan",
    }


def make_chunk(chunk_id: str, section: str, text: str) -> FilingChunk:
    return {
        "chunk_id": chunk_id,
        "ticker": "AAPL",
        "accession_number": "0000320193-23-000106",
        "filing_type": "10-K",
        "filing_date": "2023-11-03",
        "section": section,
        "text": text,
        "page": 0,
    }
