from __future__ import annotations

import html
import re
from typing import Pattern

from src.audit import append_audit_entry
from src.state import AgentState, FilingChunk, RetrievalPlan
from src.tools.edgar import EdgarClient

TICKER_TO_CIK = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
    "META": "0001326801",
    "TSLA": "0001318605",
    "NVDA": "0001045810",
}

SECTION_PATTERNS: dict[str, tuple[Pattern[str], Pattern[str]]] = {
    "Item 1A - Risk Factors": (
        re.compile(r"\bitem\s+1a[\.\s:-]+risk\s+factors\b", re.IGNORECASE),
        re.compile(r"\bitem\s+1b\b|\bitem\s+2\b", re.IGNORECASE),
    ),
    "Item 7 - Management's Discussion and Analysis": (
        re.compile(r"\bitem\s+7[\.\s:-]+management'?s\s+discussion\s+and\s+analysis\b", re.IGNORECASE),
        re.compile(r"\bitem\s+7a\b|\bitem\s+8\b", re.IGNORECASE),
    ),
    "Item 8 - Financial Statements": (
        re.compile(r"\bitem\s+8[\.\s:-]+financial\s+statements\b", re.IGNORECASE),
        re.compile(r"\bitem\s+9\b", re.IGNORECASE),
    ),
}


def retrieval_agent_node(state: AgentState) -> dict[str, object]:
    plan = state["plan"]
    if plan is None:
        return {
            "retrieved_chunks": [],
            "audit_log": append_audit_entry(state, node="retrieval_agent", notes="No retrieval plan available."),
        }

    chunks = retrieve_structural_chunks(plan)
    return {
        "retrieved_chunks": chunks,
        "audit_log": append_audit_entry(
            state,
            node="retrieval_agent",
            notes=f"Retrieved {len(chunks)} structural filing chunk(s).",
            retrieval_query=state["user_query"],
            metadata_filters={
                "ticker": plan["ticker"],
                "filing_type": plan["filing_type"],
                "sections": plan["sections"],
            },
            retrieved_chunk_ids=[chunk["chunk_id"] for chunk in chunks],
        ),
    }


def retrieve_structural_chunks(plan: RetrievalPlan, client: EdgarClient | None = None) -> list[FilingChunk]:
    cik = TICKER_TO_CIK.get(plan["ticker"])
    if cik is None:
        return []

    edgar_client = client or EdgarClient()
    metadata = edgar_client.get_latest_filing_metadata(cik, plan["filing_type"])
    if metadata is None:
        return []

    filing_text = normalize_filing_text(edgar_client.get_filing_text(metadata))
    chunks: list[FilingChunk] = []

    for section in plan["sections"]:
        section_text = extract_section_text(filing_text, section)
        if not section_text:
            continue

        chunks.append(
            {
                "chunk_id": build_chunk_id(plan["ticker"], metadata["accession_number"], section, len(chunks) + 1),
                "ticker": plan["ticker"],
                "accession_number": metadata["accession_number"],
                "filing_type": metadata["filing_type"],
                "filing_date": metadata["filing_date"],
                "section": section,
                "text": section_text,
                "page": 0,
            }
        )

    return chunks


def normalize_filing_text(raw_text: str) -> str:
    without_scripts = re.sub(r"<(script|style)\b.*?</\1>", " ", raw_text, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    decoded = html.unescape(without_tags)
    return re.sub(r"\s+", " ", decoded).strip()


def extract_section_text(filing_text: str, section: str) -> str | None:
    patterns = SECTION_PATTERNS.get(section)
    if patterns is None:
        return None

    start_pattern, end_pattern = patterns
    start_match = start_pattern.search(filing_text)
    if start_match is None:
        return None

    end_match = end_pattern.search(filing_text, start_match.end())
    end_index = end_match.start() if end_match else len(filing_text)
    return filing_text[start_match.start() : end_index].strip()


def build_chunk_id(ticker: str, accession_number: str, section: str, index: int) -> str:
    section_slug = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-")
    accession_slug = accession_number.replace("-", "")
    return f"{ticker}:{accession_slug}:{section_slug}:{index}"
