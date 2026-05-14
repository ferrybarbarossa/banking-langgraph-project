import re

from src.audit import append_audit_entry
from src.state import AgentState, RetrievalPlan

COMPANY_ALIASES = {
    "apple": "AAPL",
    "apple inc": "AAPL",
    "microsoft": "MSFT",
    "microsoft corp": "MSFT",
    "amazon": "AMZN",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "meta": "META",
    "tesla": "TSLA",
    "nvidia": "NVDA",
}

KNOWN_TICKERS = set(COMPANY_ALIASES.values())


def plan_query(query: str) -> RetrievalPlan:
    normalized_query = query.lower()

    filing_type = "10-K"
    if "10-q" in normalized_query or "quarter" in normalized_query:
        filing_type = "10-Q"
    elif "8-k" in normalized_query or "current report" in normalized_query:
        filing_type = "8-K"

    ticker = _extract_ticker(query)
    sections = _infer_sections(normalized_query)

    return {
        "ticker": ticker,
        "filing_type": filing_type,
        "sections": sections,
        "reasoning": (
            f"Mapped query to {ticker} {filing_type}; selected structural sections: {', '.join(sections)}."
        ),
    }


def planner_node(state: AgentState) -> dict[str, object]:
    plan = plan_query(state["user_query"])
    return {
        "plan": plan,
        "audit_log": append_audit_entry(
            state,
            node="planner",
            notes=plan["reasoning"],
            retrieval_query=state["user_query"],
        ),
    }


def _extract_ticker(query: str) -> str:
    normalized_query = query.lower()
    for alias, ticker in COMPANY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized_query):
            return ticker

    for candidate in re.findall(r"\b[A-Z]{1,5}\b", query):
        if candidate in KNOWN_TICKERS:
            return candidate

    return "UNKNOWN"


def _infer_sections(normalized_query: str) -> list[str]:
    if any(term in normalized_query for term in ("risk", "risks", "risk factor", "risk disclosure")):
        return ["Item 1A - Risk Factors"]

    if any(term in normalized_query for term in ("debt", "liquidity", "cash flow", "operations")):
        return ["Item 7 - Management's Discussion and Analysis"]

    if any(term in normalized_query for term in ("earnings", "revenue", "income", "financial statements")):
        return ["Item 8 - Financial Statements"]

    return ["Item 1A - Risk Factors"]
