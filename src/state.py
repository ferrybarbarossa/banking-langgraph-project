from typing import List, Literal, Optional, TypedDict


class FilingChunk(TypedDict):
    chunk_id: str
    ticker: str
    accession_number: str
    filing_type: str
    filing_date: str
    section: str
    text: str
    page: int


class ScoredChunk(TypedDict):
    chunk: FilingChunk
    similarity_score: float
    retrieval_rank: int


class Citation(TypedDict):
    chunk_id: str
    accession_number: str
    section: str
    page: int


class RetrievalPlan(TypedDict):
    ticker: str
    filing_type: Literal["10-K", "10-Q", "8-K"]
    sections: List[str]
    reasoning: str


class ComplianceVerdict(TypedDict):
    verdict: Literal["pass", "flag_for_human", "reject"]
    triggered_rules: List[str]
    reasoning: str


class AuditEntry(TypedDict):
    timestamp: str
    node: str
    model: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    retrieval_query: Optional[str]
    metadata_filters: Optional[dict]
    retrieved_chunk_ids: Optional[List[str]]
    similarity_scores: Optional[List[float]]
    retrieval_rank_ordering: Optional[List[int]]
    compliance_rules_triggered: Optional[List[str]]
    human_decision: Optional[Literal["approve", "reject"]]
    revision_count: int
    notes: str


class AgentState(TypedDict):
    user_query: str
    plan: Optional[RetrievalPlan]
    retrieved_chunks: List[FilingChunk]
    top_k_chunks: List[ScoredChunk]
    draft_answer: Optional[str]
    citations: List[Citation]
    compliance_result: Optional[ComplianceVerdict]
    human_decision: Optional[Literal["approve", "reject"]]
    human_feedback: Optional[str]
    revision_count: int
    final_answer: Optional[str]
    audit_log: List[AuditEntry]
