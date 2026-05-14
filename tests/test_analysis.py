from src.nodes.analysis import synthesize_cited_answer
from src.state import FilingChunk, ScoredChunk


def test_synthesize_cited_answer_uses_only_top_k_chunks() -> None:
    scored_chunks = [
        make_scored_chunk(
            chunk_id="AAPL:0001:item-1a-risk-factors:1:part-1",
            text="Apple says supply chain disruption can materially affect product availability.",
            rank=1,
        ),
        make_scored_chunk(
            chunk_id="AAPL:0001:item-1a-risk-factors:1:part-2",
            text="Apple also describes platform concentration and component sourcing risks.",
            rank=2,
        ),
    ]

    draft_answer, citations = synthesize_cited_answer("What are Apple's risks?", scored_chunks)

    assert "supply chain disruption" in draft_answer
    assert "platform concentration" in draft_answer
    assert "[1]" in draft_answer
    assert "[2]" in draft_answer
    assert citations == [
        {
            "chunk_id": "AAPL:0001:item-1a-risk-factors:1:part-1",
            "accession_number": "0000320193-23-000106",
            "section": "Item 1A - Risk Factors",
            "page": 0,
        },
        {
            "chunk_id": "AAPL:0001:item-1a-risk-factors:1:part-2",
            "accession_number": "0000320193-23-000106",
            "section": "Item 1A - Risk Factors",
            "page": 0,
        },
    ]


def test_synthesize_cited_answer_handles_no_evidence() -> None:
    draft_answer, citations = synthesize_cited_answer("What are Apple's risks?", [])

    assert "No relevant filing evidence" in draft_answer
    assert citations == []


def make_scored_chunk(chunk_id: str, text: str, rank: int) -> ScoredChunk:
    chunk: FilingChunk = {
        "chunk_id": chunk_id,
        "ticker": "AAPL",
        "accession_number": "0000320193-23-000106",
        "filing_type": "10-K",
        "filing_date": "2023-11-03",
        "section": "Item 1A - Risk Factors",
        "text": text,
        "page": 0,
    }
    return {
        "chunk": chunk,
        "similarity_score": 1.0 / rank,
        "retrieval_rank": rank,
    }
