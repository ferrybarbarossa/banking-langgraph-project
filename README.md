# Compliance-Aware SEC Filing Analyst

A LangGraph-based multi-agent system that answers natural-language questions about US public company filings retrieved from SEC EDGAR. Every answer is cited, retrieval and compliance decisions are audited, and every draft passes through compliance review before delivery.

**This is a reference implementation** — not intended for real investment use, client work, or production deployment.

---

## Architecture

```
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

### Agents

| Agent                  | Responsibility                                                    |
| ---------------------- | ----------------------------------------------------------------- |
| **Planner**            | Interprets the query, selects filing type and sections to target  |
| **Retrieval Agent**    | Locates the correct filing section structurally from SEC EDGAR    |
| **Semantic Retrieval** | Chunks, embeds, and ranks content within the bounded section      |
| **Analysis Agent**     | Synthesizes a cited answer from top-k retrieved chunks            |
| **Compliance Reviewer**| Enforces citation, grounding, and content-policy rules            |
| **Human Review**       | Pauses the graph for manual approval when compliance flags output |

### Hybrid Retrieval

Retrieval is two-stage:

1. **Structural** — identify the correct filing section (e.g., Item 1A — Risk Factors)
2. **Semantic** — chunk, embed, apply metadata filters, and rank by similarity within that section

This improves retrieval precision, citation accuracy, and hallucination resistance.

---

## Tech Stack

| Component      | Choice                                   |
| -------------- | ---------------------------------------- |
| Orchestration  | LangGraph >= 0.2                         |
| LLM config     | Claude Sonnet 4.5 / Claude Opus 4.5 or GPT-5 (configurable via `LLM_PROVIDER`) |
| Vector store   | ChromaDB >= 0.5                          |
| Embeddings     | sentence-transformers (all-MiniLM-L6-v2) |
| Persistence    | LangGraph SqliteSaver                    |
| Validation     | Pydantic >= 2                            |
| Logging        | structlog                                |
| Testing        | pytest                                   |
| Python         | 3.11+                                    |

---

## Setup

### Prerequisites

- Python 3.11+
- An Anthropic API key, or an OpenAI API key (depending on `LLM_PROVIDER`)

### Install

```bash
git clone <repo-url>
cd banking-langgraph-project
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

For development and evaluation:

```bash
pip install -e ".[dev]"
```

### Configure

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Required environment variables:

| Variable             | Description                                                                |
| -------------------- | -------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY`  | Anthropic API key (required when `LLM_PROVIDER=anthropic`, the default)    |
| `OPENAI_API_KEY`     | OpenAI API key (required when `LLM_PROVIDER=openai`)                       |
| `LLM_PROVIDER`       | `anthropic` (default) or `openai` — selects the model provider at runtime  |
| `ANTHROPIC_MODEL`    | Override default Anthropic model (default `claude-sonnet-4-5`)             |
| `OPENAI_MODEL`       | Override default OpenAI model (default `gpt-5`)                            |
| `USER_AGENT`         | Descriptive SEC EDGAR User-Agent string                                    |

---

## Usage

### Run the demo

```bash
python examples/demo.py
```

If compliance returns `flag_for_human`, the demo prints the draft, triggered rules, and reviewer reasoning, then asks for an approve/reject decision before resuming the graph from the SQLite checkpoint.

### Example queries

| Query                                                        | Expected behavior                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| "What were Apple's biggest risk disclosures in their latest 10-K?" | Returns cited summary from Risk Factors section              |
| "Should I buy Apple stock?"                                  | Compliance flags as investment advice; human review triggered |
| "What were Acme Corp's earnings?"                            | Returns "no data found" gracefully; no hallucination         |

Queries are bounded to 500 characters maximum.

---

## Compliance Rules

All outputs pass through deterministic compliance checks before delivery:

| Rule  | Description                                | Action         |
| ----- | ------------------------------------------ | -------------- |
| C-001 | Buy/sell advice detection                  | flag_for_human |
| C-002 | Investment recommendation language         | flag_for_human |
| C-003 | Missing citations                          | reject         |
| C-004 | Forward-looking statements                 | flag_for_human |
| C-005 | Unsupported company references             | reject         |
| C-006 | Runaway response length                    | reject         |
| C-007 | Citation not grounded in retrieved chunks  | reject         |

Ambiguous cases that pass deterministic checks are routed to an LLM judge.

---

## Evaluation

Run the evaluation harness:

```bash
pytest tests/evals/
```

Run the full local release gate:

```bash
ruff check
pytest tests/evals/
pytest tests/
```

Evaluations assert **properties**, not exact strings:

```yaml
- compliance_verdict: pass
- has_citations: true
- citation_count: ">= 1"
- answer_word_count: "< 500"
- all_citations_resolve_to_top_k: true
```

No prompt, retrieval, model, or policy change ships without a passing eval run.

---

## Development Workflow

The project follows **GitHub Flow with phase branches**, scoped to the build phases defined in SPEC §12.

| Convention      | Choice                                                                  |
| --------------- | ----------------------------------------------------------------------- |
| Trunk           | `main` — every commit corresponds to a completed phase deliverable      |
| Phase branches  | `phase/<n>-<slug>` (e.g., `phase/2-edgar-retrieval`)                    |
| Other branches  | `fix/<slug>` for bug fixes, `docs/<slug>` for spec/docs updates         |
| Merge style     | Squash-merge via PR — one commit per phase on `main`                    |
| Tags            | `v0.1-phase1`, `v0.2-phase2`, …, `v1.0` at Phase 9 completion           |
| Release gate    | `pytest tests/evals/` green before any merge into `main`                |
| Auth            | `gh auth setup-git` routes pushes through the GitHub account credential |

The release gate operationalizes the evaluation discipline above: no prompt, retrieval, model, or policy change reaches `main` without a passing eval run.

Out of scope (deferred until after Phase 9): CI/CD, pre-commit hooks, branch protection rules, container builds, signed commits.

See [SPEC.md §13](SPEC.md) for the full DevOps plan.

---

## Project Structure

```
├── README.md
├── SPEC.md
├── pyproject.toml
├── .env.example
├── src/
│   ├── graph.py              # Graph wiring
│   ├── state.py              # AgentState schema
│   ├── audit.py              # Audit trail logger
│   ├── config.py             # Configuration
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
│   │   ├── edgar.py          # SEC EDGAR API client
│   │   └── chunker.py        # Text chunking
│   ├── prompts/
│   └── policies/
├── tests/
│   ├── evals/
│   ├── test_compliance.py
│   ├── test_semantic_retrieval.py
│   ├── test_graph.py
│   └── test_phase7_interrupts.py
└── examples/
    └── demo.py
```

---

## Key Design Decisions

- **Hybrid retrieval** — structural boundaries before semantic search reduces noisy retrievals and context-window dilution
- **Retrieval grounding (C-007)** — citation traceability is enforced architecturally, not by prompt discipline
- **Loop protection** — after 3 revision cycles, the graph forces human review to prevent infinite loops
- **Audit trail** — every model call, retrieval, and compliance decision is logged as structured JSONL
- **State persistence** — SqliteSaver checkpoints at every node boundary for interrupt/resume and replay

---

## What This Project Demonstrates

- Governed multi-agent orchestration with LangGraph
- Hybrid retrieval (structural + semantic)
- Compliance-gated output with deterministic and LLM-judge layers
- Human-in-the-loop interrupt/resume patterns
- Full audit trail and retrieval traceability
- Property-based evaluation discipline

## What This Project Does NOT Demonstrate

- Production MLOps or enterprise authorization
- Production-scale vector infrastructure or observability
- Adversarial prompt-injection defenses
- Domain-authoritative banking compliance
- Multi-user concurrent operation

These omissions are intentional. See [SPEC.md](SPEC.md) for the full specification.

---

## License

This project is for demonstration and portfolio purposes.

## Author

Mohamed (Ferry) Erouk
