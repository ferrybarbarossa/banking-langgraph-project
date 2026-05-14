from __future__ import annotations

import re

from src.audit import append_audit_entry
from src.state import AgentState, Citation, ComplianceVerdict, ScoredChunk

MAX_ANSWER_WORDS = 500

BUY_SELL_PATTERN = re.compile(r"\b(should\s+i\s+)?(buy|sell|hold)\b", re.IGNORECASE)
RECOMMENDATION_PATTERN = re.compile(
    r"\b(recommend|recommendation|outperform|underperform|price target|strong buy|strong sell)\b",
    re.IGNORECASE,
)
FORWARD_LOOKING_PATTERN = re.compile(
    r"\b(will|forecast|predict|projection|next quarter|next year|future growth|grow next)\b",
    re.IGNORECASE,
)
KNOWN_COMPANY_REFERENCES = {
    "AAPL": {"apple", "aapl"},
    "MSFT": {"microsoft", "msft"},
    "AMZN": {"amazon", "amzn"},
    "GOOGL": {"alphabet", "google", "googl"},
    "META": {"meta", "facebook"},
    "TSLA": {"tesla", "tsla"},
    "NVDA": {"nvidia", "nvda"},
}


def compliance_reviewer_node(state: AgentState) -> dict[str, object]:
    compliance_result = review_compliance(state)
    return {
        "compliance_result": compliance_result,
        "audit_log": append_audit_entry(
            state,
            node="compliance_reviewer",
            notes=compliance_result["reasoning"],
            compliance_rules_triggered=compliance_result["triggered_rules"],
        ),
    }


def review_compliance(state: AgentState) -> ComplianceVerdict:
    draft_answer = state["draft_answer"] or ""
    triggered_rules: list[str] = []
    reasoning: list[str] = []

    if state["revision_count"] >= 3:
        return {
            "verdict": "flag_for_human",
            "triggered_rules": ["C-LOOP"],
            "reasoning": "Revision limit reached; escalating to human review.",
        }

    if _contains_buy_sell_advice(state["user_query"], draft_answer):
        triggered_rules.append("C-001")
        reasoning.append("Query or draft asks for buy/sell/hold advice.")

    if RECOMMENDATION_PATTERN.search(draft_answer):
        triggered_rules.append("C-002")
        reasoning.append("Draft contains investment recommendation language.")

    if _missing_required_citations(draft_answer, state["top_k_chunks"], state["citations"]):
        triggered_rules.append("C-003")
        reasoning.append("Draft has retrieved evidence but missing citation markers or citation objects.")

    if FORWARD_LOOKING_PATTERN.search(f"{state['user_query']} {draft_answer}"):
        triggered_rules.append("C-004")
        reasoning.append("Query or draft contains forward-looking language.")

    if _has_unsupported_company_reference(draft_answer, state["top_k_chunks"]):
        triggered_rules.append("C-005")
        reasoning.append("Draft references a company not represented in retrieved evidence.")

    if len(draft_answer.split()) > MAX_ANSWER_WORDS:
        triggered_rules.append("C-006")
        reasoning.append("Draft answer exceeds the maximum allowed word count.")

    if _has_ungrounded_citation(state["citations"], state["top_k_chunks"]):
        triggered_rules.append("C-007")
        reasoning.append("One or more citations do not resolve to current top-k chunks.")

    return _verdict_for_rules(triggered_rules, reasoning)


def _contains_buy_sell_advice(query: str, draft_answer: str) -> bool:
    return BUY_SELL_PATTERN.search(query) is not None or BUY_SELL_PATTERN.search(draft_answer) is not None


def _missing_required_citations(draft_answer: str, top_k_chunks: list[ScoredChunk], citations: list[Citation]) -> bool:
    if not top_k_chunks:
        return False

    citation_markers = re.findall(r"\[\d+\]", draft_answer)
    return not citations or not citation_markers


def _has_unsupported_company_reference(draft_answer: str, top_k_chunks: list[ScoredChunk]) -> bool:
    if not top_k_chunks:
        return False

    supported_tickers = {scored["chunk"]["ticker"] for scored in top_k_chunks}
    supported_terms = set().union(
        *(KNOWN_COMPANY_REFERENCES.get(ticker, {ticker.lower()}) for ticker in supported_tickers)
    )
    referenced_terms = {
        term
        for terms in KNOWN_COMPANY_REFERENCES.values()
        for term in terms
        if re.search(rf"\b{re.escape(term)}\b", draft_answer, re.IGNORECASE)
    }
    return bool(referenced_terms - supported_terms)


def _has_ungrounded_citation(citations: list[Citation], top_k_chunks: list[ScoredChunk]) -> bool:
    top_k_chunk_ids = {scored["chunk"]["chunk_id"] for scored in top_k_chunks}
    return any(citation["chunk_id"] not in top_k_chunk_ids for citation in citations)


def _verdict_for_rules(triggered_rules: list[str], reasoning: list[str]) -> ComplianceVerdict:
    reject_rules = {"C-003", "C-005", "C-006", "C-007"}
    human_rules = {"C-001", "C-002", "C-004"}

    if any(rule in reject_rules for rule in triggered_rules):
        verdict = "reject"
    elif any(rule in human_rules for rule in triggered_rules):
        verdict = "flag_for_human"
    else:
        verdict = "pass"
        reasoning.append("Deterministic compliance checks passed.")

    return {
        "verdict": verdict,
        "triggered_rules": triggered_rules,
        "reasoning": " ".join(reasoning),
    }
