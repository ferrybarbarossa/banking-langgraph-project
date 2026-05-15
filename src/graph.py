import sqlite3
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from src.nodes.analysis import analysis_agent_node
from src.nodes.compliance import compliance_reviewer_node
from src.nodes.human_review import human_review_node
from src.nodes.output import output_node
from src.nodes.planner import planner_node
from src.nodes.retrieval import retrieval_agent_node
from src.nodes.semantic_retrieval import semantic_retrieval_node
from src.state import AgentState

DEFAULT_CHECKPOINT_DB = Path(".cache") / "checkpoints.sqlite"


def make_initial_state(query: str) -> AgentState:
    return {
        "user_query": query,
        "plan": None,
        "retrieved_chunks": [],
        "top_k_chunks": [],
        "draft_answer": None,
        "citations": [],
        "compliance_result": None,
        "human_decision": None,
        "human_feedback": None,
        "revision_count": 0,
        "final_answer": None,
        "audit_log": [],
    }


def build_graph(checkpointer: SqliteSaver | None = None) -> object:
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("retrieval_agent", retrieval_agent_node)
    graph_builder.add_node("semantic_retrieval", semantic_retrieval_node)
    graph_builder.add_node("analysis_agent", analysis_agent_node)
    graph_builder.add_node("compliance_reviewer", compliance_reviewer_node)
    graph_builder.add_node("human_review", human_review_node)
    graph_builder.add_node("output", output_node)
    graph_builder.set_entry_point("planner")
    graph_builder.add_edge("planner", "retrieval_agent")
    graph_builder.add_edge("retrieval_agent", "semantic_retrieval")
    graph_builder.add_edge("semantic_retrieval", "analysis_agent")
    graph_builder.add_edge("analysis_agent", "compliance_reviewer")
    graph_builder.add_conditional_edges(
        "compliance_reviewer",
        route_after_compliance,
        {
            "output": "output",
            "human_review": "human_review",
            "analysis_agent": "analysis_agent",
        },
    )
    graph_builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "output": "output",
            "analysis_agent": "analysis_agent",
        },
    )
    graph_builder.add_edge("output", END)
    return graph_builder.compile(checkpointer=checkpointer)


def route_after_compliance(state: AgentState) -> str:
    compliance_result = state["compliance_result"]
    if compliance_result is None:
        return "output"

    if compliance_result["verdict"] == "pass":
        return "output"

    if compliance_result["verdict"] == "flag_for_human" or state["revision_count"] >= 3:
        return "human_review"

    return "analysis_agent"


def route_after_human_review(state: AgentState) -> str:
    if state["human_decision"] == "approve":
        return "output"
    return "analysis_agent"


@lru_cache(maxsize=1)
def _compiled_graph() -> object:
    return build_graph(default_checkpointer())


@lru_cache(maxsize=1)
def default_checkpointer() -> SqliteSaver:
    DEFAULT_CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DEFAULT_CHECKPOINT_DB, check_same_thread=False)
    return SqliteSaver(connection)


def run_graph(query: str, *, thread_id: str = "default") -> AgentState:
    return _compiled_graph().invoke(make_initial_state(query), config=thread_config(thread_id))


def resume_graph(
    *,
    decision: str,
    feedback: str | None = None,
    thread_id: str = "default",
) -> AgentState:
    return _compiled_graph().invoke(
        Command(resume={"decision": decision, "feedback": feedback}),
        config=thread_config(thread_id),
    )


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}
