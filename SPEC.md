# SPEC.md V1.3

**Project:** Compliance-Aware SEC Filing Analyst
**Status:** Specification — Phase 7 implemented
**Owner:** Mohamed (Ferry) Erouk
**Last updated:** 2026-05-13
**Revision:** v1.8 — Phase 7 human-review interrupt and SQLite checkpoint persistence implemented

---

# 1. Purpose

A LangGraph-based multi-agent system that answers natural-language questions about US public company filings retrieved from SEC EDGAR.

Retrieval is hybrid:

1. the system first locates the relevant filing section structurally
2. then performs semantic retrieval within that bounded section using a local vector store

Every answer is cited, every model call is logged, and every output passes through a compliance review before being returned. When compliance flags an output, the graph pauses for human review.

The workflow intentionally requires:

* branching logic
* state persistence
* compliance gating
* interrupt/resume behavior
* iterative revision loops
* human escalation

making graph-based orchestration appropriate.

It is **not** intended for:

* real investment use
* real client work
* production banking deployment
* operation on proprietary financial data

---

# 2. Non-Goals

The following are deliberately out of scope:

* Investment advice or recommendations of any kind
* Real-time market data, pricing, or analyst forecasts
* Comparison or aggregation across multiple companies in a single answer
* Forward-looking projections beyond what is stated in the source filing
* Any integration with proprietary or licensed data sources
* A user interface beyond a CLI demo
* Multi-user authentication or authorization
* Production deployment
* Enterprise authorization models
* Production-scale observability or MLOps

If any of these are needed later, they require a separate specification.

---

# 3. Users and Use Cases

## Primary user

An informed technical reviewer (engineering manager, AI lead, interviewer) evaluating the author's command of:

* hybrid RAG architectures
* LangGraph orchestration
* governed AI workflows
* evaluation discipline
* compliance-aware AI patterns

Secondary users may include analysts using the demo to retrieve information from public filings.

---

## Use cases

| Use case           | Example query                                                      | Expected behavior                                                   |
| ------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------- |
| Standard retrieval | "What were Apple's biggest risk disclosures in their latest 10-K?" | Returns cited summary from Risk Factors section                     |
| Out-of-scope       | "Should I buy Apple stock?"                                        | Compliance flags as investment advice; human review interrupts      |
| Insufficient data  | "What were Acme Corp's earnings?"                                  | Returns "no data found" gracefully; no hallucination                |
| Ambiguous          | "Tell me about Apple's debt"                                       | Answer specifies filing and year; does not aggregate across filings |
| Forward-looking    | "Will Apple grow next quarter?"                                    | Compliance flags; human review                                      |
| Missing citation   | internal citation failure                                          | Compliance rejects before output                                    |

---

# 4. Functional Requirements

## FR-1 — Natural language query intake

The system accepts a free-form natural language question via CLI.

The query is bounded to 500 characters maximum to reduce:

* prompt-injection surface area
* accidental oversized prompts
* unbounded retrieval requests

---

## FR-2 — Filing retrieval

The system retrieves filings from SEC EDGAR using the public REST API at `data.sec.gov`.

Supported filing types:

* 10-K
* 10-Q
* 8-K

The retrieval layer:

* respects EDGAR rate limits
* includes a descriptive User-Agent header
* supports local filing caching

---

## FR-3 — Multi-agent analysis

The system uses at minimum:

* a **Planner**
* a **Retrieval Agent**
* an **Analysis Agent**
* a **Compliance Reviewer**

Each agent:

* has a role-bounded system prompt
* returns structured output
* uses Pydantic validation
* does not return unrestricted free-form responses

---

## FR-3a — Hybrid retrieval (structural + semantic)

The retrieval pipeline is hybrid.

### Step 1 — Structural retrieval

The Retrieval Agent first identifies the correct filing section structurally.

Examples:

* Item 1A — Risk Factors
* Management Discussion and Analysis
* Financial Statements

This bounds the retrieval space deterministically.

### Step 2 — Semantic retrieval

Within the structurally bounded section:

* content is chunked
* chunks are embedded
* deterministic metadata filters (ticker, filing_type, accession_number, filing_date) are applied **before** semantic ranking
* semantic similarity search retrieves the top-k relevant chunks

The semantic layer operates as follows:

* Chunking uses `RecursiveCharacterTextSplitter`
* Chunk size defaults to 1000 tokens
* Overlap defaults to 100 tokens
* Embeddings use a lightweight local sentence-transformer model
* Chunks are stored in a query-bounded ephemeral ChromaDB collection
* Semantic retrieval returns top-k chunks (default k=5)
* Only top-k retrieved chunks are passed to the Analysis Agent

The hybrid strategy intentionally combines:

* deterministic retrieval boundaries
* metadata-constrained filtering
* semantic relevance ranking

This improves:

* retrieval precision
* citation accuracy
* token efficiency
* hallucination resistance

while reducing:

* noisy retrievals
* context-window dilution
* semantically similar but structurally irrelevant matches

The Analysis Agent may synthesize only from retrieved chunks returned by the retrieval pipeline. This is enforced architecturally by compliance rule C-007 (see Section 9), not relied upon as a stylistic discipline of the model.

---

## FR-3b — Retrieval traceability

Every retrieved chunk remains traceable throughout the workflow.

Each retrieval result includes:

* ticker
* accession number
* filing type
* filing date
* section name
* chunk identifier
* semantic similarity score
* retrieval rank

The audit layer records:

* retrieval query
* metadata filters
* top-k selection
* similarity scores
* selected chunk identifiers

This exists to support:

* auditability
* reproducibility
* retrieval-grounded generation
* compliance defensibility

---

## FR-3c — Filing cache

Retrieved filings are cached locally after first retrieval to:

* reduce SEC EDGAR load
* improve evaluation reproducibility
* reduce latency
* reduce repeated retrieval cost
* support deterministic replay during debugging

Cached filings are treated as immutable snapshots during a single evaluation run.

---

## FR-4 — Citation enforcement

Every factual claim in the final answer must include a citation pointing to:

* filing
* section
* chunk
* page when available

Claims without citations are rejected by the compliance layer.

---

## FR-5 — Compliance review

Every draft answer passes through a Compliance Reviewer before being returned.

The reviewer operates in two layers:

### Layer 1 — Deterministic checks

Examples:

* investment-advice detection
* missing citations
* unsupported company references
* excessive response length
* forward-looking language
* citation traceability to retrieved chunks

### Layer 2 — LLM judge

Used only for ambiguous cases.

Compliance verdicts are:

* `pass`
* `flag_for_human`
* `reject`

---

## FR-6 — Human-in-the-loop interrupt

When compliance returns `flag_for_human`:

* the graph pauses using LangGraph interrupts
* the CLI displays:

  * draft answer
  * triggered rules
  * reviewer reasoning
* a reviewer may:

  * approve
  * reject

On reject:

* the graph loops back to Analysis Agent
* reviewer feedback is injected into state

---

## FR-7 — State persistence

The graph uses `SqliteSaver` for checkpoint persistence.

State persists at every node boundary.

This enables:

* interrupt/resume behavior
* replayability
* debugging
* evaluation reproducibility

---

## FR-8 — Audit trail

Every model call writes a structured audit entry.

The audit entry schema is enforced (see Section 6.2) and includes:

* timestamp
* node name
* model identifier
* token counts
* retrieval query
* metadata filters applied
* retrieved chunk identifiers
* similarity scores
* retrieval rank ordering
* compliance rule triggers
* revision count
* human-review decisions
* retry paths

Audit logs are written as JSONL.

In production, this would route to centralized observability infrastructure.

---

## FR-9 — Evaluation harness

A pytest-based evaluation harness runs the graph against a fixed evaluation suite.

The evaluation suite asserts properties, not exact output strings.

Evaluation covers:

* retrieval correctness
* citation correctness
* hallucination prevention
* compliance behavior
* interrupt behavior
* audit completeness

The eval harness acts as a release gate for:

* prompt changes
* model changes
* retrieval changes
* policy changes

---

# 5. Non-Functional Requirements

## NFR-1 — Reproducibility

Given:

* the same input query
* the same model version
* the same filing snapshot

The audit trail must allow reconstruction of graph execution.

Reproducibility is a load-bearing system property.

---

## NFR-2 — Latency

A standard query should complete in under 60 seconds on a developer machine.

This is a soft target.

Correctness and traceability take priority over latency.

---

## NFR-3 — Cost

A single query should cost under $0.20 using Claude Sonnet.

A full eval run should cost under $5.

These are discipline constraints, not hard guarantees.

---

## NFR-4 — Maintainability

The system enforces separation of concerns.

Requirements:

* prompts stored separately
* policies stored separately
* independently testable nodes
* graph wiring isolated from business logic
* retrieval isolated from orchestration
* audit layer isolated from node logic

---

## NFR-5 — Documentation

A stranger must be able to:

* clone the repo
* install dependencies
* configure environment variables
* run the demo
* execute evals

within approximately 10 minutes.

README must include:

* purpose
* install instructions
* architecture overview
* example queries
* environment variables
* evaluation instructions

---

## NFR-6 — Retrieval evaluation quality

Retrieval quality is treated as a first-class system concern.

Metrics include:

* citation correctness
* chunk relevance
* retrieval precision
* unsupported-claim rate
* hallucination rate
* semantic retrieval stability

The evaluation harness validates:

* final answers
* retrieval evidence quality
* retrieval grounding consistency

---

# 6. Architecture

## 6.1 Graph topology

```text
        User Query
             │
             ▼
         Planner
             │
             ▼
     Retrieval Agent
   (structural retrieval)
             │
             ▼
    Semantic Retrieval
 (chunk + embed + top-k)
             │
             ▼
      Analysis Agent
             │
             ▼
    Compliance Reviewer
       ┌─────┼─────┐
       │     │     │
      pass  flag  reject
       │     │     │
       ▼     ▼     ▼
    Output Human  loop
            Review back
```

---

## 6.2 State schema

```python
from typing import TypedDict, Optional, List, Literal

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
    # LLM call fields (None for non-LLM nodes)
    model: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    # Retrieval fields (populated for retrieval and semantic nodes)
    retrieval_query: Optional[str]
    metadata_filters: Optional[dict]
    retrieved_chunk_ids: Optional[List[str]]
    similarity_scores: Optional[List[float]]
    retrieval_rank_ordering: Optional[List[int]]
    # Compliance fields (populated for compliance reviewer)
    compliance_rules_triggered: Optional[List[str]]
    # Human-in-the-loop fields (populated for human review)
    human_decision: Optional[Literal["approve", "reject"]]
    # Revision tracking
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
```

---

## 6.3 Node contracts

| Node                | Input                           | Output                  |
| ------------------- | ------------------------------- | ----------------------- |
| planner             | user_query                      | plan                    |
| retrieval_agent     | plan                            | retrieved_chunks        |
| semantic_retrieval  | user_query, retrieved_chunks    | top_k_chunks            |
| analysis_agent      | top_k_chunks                    | draft_answer, citations |
| compliance_reviewer | draft_answer, citations         | compliance_result       |
| human_review        | draft_answer, compliance_result | human_decision          |
| output              | final content                   | final_answer            |

---

## 6.4 Conditional edges

| From                | Condition      | To                 |
| ------------------- | -------------- | ------------------ |
| retrieval_agent     | chunks found   | semantic_retrieval |
| retrieval_agent     | no chunks      | output             |
| semantic_retrieval  | top-k found    | analysis_agent     |
| semantic_retrieval  | none found     | output             |
| compliance_reviewer | pass           | output             |
| compliance_reviewer | flag_for_human | human_review       |
| compliance_reviewer | reject         | analysis_agent     |
| human_review        | approve        | output             |
| human_review        | reject         | analysis_agent     |

---

## 6.5 Loop protection

The state tracks `revision_count`.

After 3 revisions:

* the graph forces `flag_for_human`
* further autonomous retries stop

This prevents infinite revision loops.

---

# 7. Tech Stack

| Component                         | Choice                                   | Rationale                                 |
| --------------------------------- | ---------------------------------------- | ----------------------------------------- |
| Orchestration                     | langgraph >= 0.2                         | Stateful graph orchestration              |
| LLM SDKs                          | langchain-anthropic, langchain-openai    | Structured-output support; multi-provider |
| Primary model (default)           | claude-sonnet-4-5                        | Development speed/quality balance         |
| Alternative model                 | gpt-5                                    | Selectable via `LLM_PROVIDER=openai`      |
| Demo model                        | claude-opus-4-5                          | Better edge-case reasoning                |
| Provider selector                 | `LLM_PROVIDER` env var (`anthropic`/`openai`) | Runtime provider switching via `src/config.py:get_llm` |
| Vector store                      | chromadb >= 0.5                          | Lightweight local vector persistence      |
| Embeddings                        | sentence-transformers (all-MiniLM-L6-v2) | Local low-cost retrieval                  |
| Enterprise retrieval alternatives | pgvector / Azure AI Search / Pinecone    | Representative production migration paths |
| Chunking                          | RecursiveCharacterTextSplitter           | Standard retrieval chunking               |
| Persistence                       | SqliteSaver                              | Local checkpoint persistence              |
| Validation                        | pydantic >= 2                            | Structured-output enforcement             |
| Logging                           | structlog                                | Structured audit logging                  |
| Testing                           | pytest                                   | Evaluation harness                        |
| Python                            | 3.11+                                    | Modern typing and LangGraph support       |

---

# 8. File Structure

```text
citi-langgraph-demo/
├── README.md
├── SPEC.md
├── pyproject.toml
├── .env.example
├── src/
│   ├── graph.py
│   ├── state.py
│   ├── audit.py
│   ├── config.py
│   ├── nodes/
│   │   ├── planner.py
│   │   ├── retrieval.py
│   │   ├── semantic_retrieval.py
│   │   ├── analysis.py
│   │   ├── compliance.py
│   │   ├── human_review.py
│   │   └── output.py
│   ├── retrieval/
│   │   ├── embeddings.py
│   │   └── vector_store.py
│   ├── tools/
│   │   ├── edgar.py
│   │   └── chunker.py
│   ├── prompts/
│   └── policies/
├── tests/
│   ├── test_compliance.py
│   ├── test_semantic_retrieval.py
│   ├── test_graph.py
│   └── evals/
└── examples/
    └── demo.py
```

---

# 9. Compliance Rules

## Deterministic rules

| Rule  | Description                                                | Action         |
| ----- | ---------------------------------------------------------- | -------------- |
| C-001 | "buy" / "sell" advice                                      | flag_for_human |
| C-002 | investment recommendation language                         | flag_for_human |
| C-003 | missing citations                                          | reject         |
| C-004 | forward-looking statements                                 | flag_for_human |
| C-005 | unsupported company references                             | reject         |
| C-006 | runaway response length                                    | reject         |
| C-007 | citation chunk_id not found in `top_k_chunks` (ungrounded) | reject         |

Rule C-007 is the architectural enforcement of retrieval grounding (FR-3a). Any factual claim whose citation does not resolve to a chunk_id present in the current state's `top_k_chunks` is rejected. This is what makes "the Analysis Agent must synthesize only from retrieved chunks" a structural property of the system rather than a prompt-engineering preference.

---

## LLM judge

Used only for ambiguous cases after deterministic checks pass.

The judge returns:

* pass
* flag_for_human
* reject

with reasoning.

---

# 10. Prompt Engineering Standards

Requirements:

1. role-bounded prompts
2. structured outputs
3. defensive instructions
4. explicit failure behavior
5. reasoning isolated from user-visible answers
6. prompt versioning
7. evaluation-tracked revisions

Prompt files begin with:

```markdown
# Prompt: Planner v1.2
# Last updated: 2026-05-13
# Eval pass rate: 14/15
```

---

# 11. Evaluation Strategy

## Eval composition

The evaluation set contains:

* happy-path retrievals
* investment-advice queries
* insufficient-data queries
* ambiguous queries
* forward-looking queries
* citation-failure injections
* ungrounded-citation injections (C-007 coverage)

---

## Assertion style

Evaluations assert properties rather than exact strings.

Example:

```yaml
- compliance_verdict: pass
- has_citations: true
- citation_count: ">= 2"
- answer_word_count: "< 500"
- all_citations_resolve_to_top_k: true
```

---

## Release gate

No:

* prompt change
* retrieval change
* model change
* policy change

ships without a passing evaluation run.

---

# 12. Build Phases

| Phase | Hours | Deliverable                                                           |
| ----- | ----- | --------------------------------------------------------------------- |
| 1     | 1.5   | Graph skeleton — compiles and runs end-to-end with stub nodes         |
| 2     | 1.5   | EDGAR retrieval tool + filing cache, tested independently             |
| 3     | 2.0   | Planner + Retrieval Agent — real query produces real retrieved chunks |
| 4     | 2.5   | Hybrid semantic retrieval — chunking, embedding, ChromaDB, top-k      |
| 5     | 1.5   | Analysis Agent — end-to-end query returns cited draft answer          |
| 6     | 1.5   | Compliance Reviewer + policies (C-001 through C-007)                  |
| 7     | 1.0   | Human-in-the-loop interrupt + SQLite checkpoint persistence           |
| 8     | 1.0   | Eval harness — 10-15 cases, property-based assertions                 |
| 9     | 1.0   | README polish + audit log review + GitHub push                        |

Target total build time: **11-15 hours over 7-10 days.**

Each phase produces something runnable. The order matters — earlier phases unblock later ones. If you fall behind, the lowest-risk drop is Phase 9 polish (keep just 5 eval cases); the highest-risk drop is Phase 6 (without compliance the demo loses its differentiating story).

---

# 13. DevOps and Release Engineering

The project follows a lightweight DevOps discipline appropriate for a solo, phased, portfolio implementation. It exists to make the build phases (§12) auditable end-to-end and to give the evaluation release-gate (§11) a concrete enforcement mechanism.

---

## 13.1 Repository hosting

* GitHub: `ferrybarbarossa/banking-langgraph-project` — public.
* Default branch: `main`.

---

## 13.2 Git workflow — GitHub Flow with phase branches

Trunk: `main`. Always in a runnable state — every commit on `main` corresponds to a completed phase deliverable as defined in §12.

| Branch type | Naming                              | Example                              |
| ----------- | ----------------------------------- | ------------------------------------ |
| Phase work  | `phase/<n>-<slug>`                  | `phase/2-edgar-retrieval`            |
| Bug fix     | `fix/<slug>`                        | `fix/audit-timestamp-tz`             |
| Spec/docs   | `docs/<slug>`                       | `docs/clarify-c-007`                 |

Merge style: **squash-merge via pull request**. One commit per phase lands on `main`. This keeps the commit history aligned with the SPEC §12 phase boundaries and makes `git log main` readable as a phase progression.

Phase-boundary tagging: lightweight tags `v0.1-phase1`, `v0.2-phase2`, …, `v1.0` at Phase 9 completion.

Commit message style:
* First line under 70 characters
* Body focuses on the *why* rather than the *what*
* Co-authorship trailers preserved when relevant

---

## 13.3 Release gate

A merge from `phase/*` into `main` requires all of:

1. Passing eval run per §11 — `pytest tests/evals/` green
2. Unit tests green — `pytest tests/`
3. Audit entries produced during the eval run conform to the `AuditEntry` schema (§6.2)
4. SPEC updated in the same PR if behavior, schema, or policy changed

This makes §11's principle — *no prompt, retrieval, model, or policy change ships without a passing evaluation run* — structurally enforceable rather than merely intended.

---

## 13.4 Credentials and identity

* Git push routes through the `gh` credential helper, configured via `gh auth setup-git`. Pushes carry the GitHub account's permissions rather than stored HTTPS credentials, which prevents identity drift when multiple accounts exist on the developer machine.
* Local `git config user.name` and `user.email` must match the committing GitHub identity. A mismatch shows up as an authorship gap in `git log` (commit author ≠ pushing account) and is treated as a defect.

---

## 13.5 `.gitignore` policy

The repository ignores:

* Python bytecode — `__pycache__/`, `*.py[cod]`
* Build artifacts — `*.egg-info/`
* Tool caches — `.pytest_cache/`, `.ruff_cache/`
* Virtual environments — `.venv/`
* Secret-bearing files — `.env`

`.env.example` is checked in as the template; `.env` itself is never committed. Bytecode files that escaped a prior commit are removed via `git rm --cached` rather than left in history.

---

## 13.6 Out of scope

Deliberately deferred — appropriate next steps once Phase 9 completes, but outside the bounded scope of this reference implementation:

* CI/CD pipelines (GitHub Actions or other) — the §13.3 release gate is currently enforced manually
* Pre-commit hooks (ruff, pytest, type checking)
* Branch protection rules on `main` (required reviews, required status checks)
* Container builds and deployment automation
* Secret-scanning tooling beyond `.gitignore` discipline
* Signed commits and signed tags

These omissions are intentional and consistent with the §14 risk posture.

---

# 14. Risks and Mitigations

| Risk                     | Mitigation                                      |
| ------------------------ | ----------------------------------------------- |
| LangGraph API changes    | Pin versions                                    |
| SEC rate limits          | Local caching (FR-3c)                           |
| Retrieval quality issues | Manual validation + top-k tuning                |
| Scope creep              | Non-goals section enforced                      |
| Embedding instability    | Local deterministic embeddings                  |
| Stale Chroma collections | Query-bounded ephemeral collections             |
| Eval set becomes target  | Refresh quarterly; never tune to specific cases |

---

# 15. What This Project Does NOT Demonstrate

The project intentionally does not demonstrate:

* production MLOps
* enterprise authorization models
* production-scale vector infrastructure
* concurrent multi-user operation
* adversarial prompt-injection defenses
* advanced sparse+dense retrieval pipelines
* retrieval re-ranking
* enterprise observability stacks
* domain-authoritative banking compliance

These omissions are intentional.

The project is a bounded reference implementation focused on:

* governed orchestration
* hybrid retrieval
* auditability
* evaluation discipline
* human-in-the-loop patterns

rather than full banking-platform implementation.

---

# 16. Open Questions

Deferred decisions:

* single-turn vs multi-turn support
* Streamlit UI vs CLI-only
* standalone audit schema publication

These do not block implementation.

---

# 17. References

* LangGraph documentation
* SEC EDGAR developer documentation
* Anthropic prompt-engineering guidance
* ChromaDB documentation
* Sentence-transformers documentation

---

*This specification is the source of truth for the project. Code that conflicts with the spec is wrong by definition unless the specification itself is updated.*
