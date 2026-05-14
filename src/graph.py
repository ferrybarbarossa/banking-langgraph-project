from functools import lru_cache

from langgraph.graph import END, StateGraph

from src.audit import append_audit_entry
from src.state import AgentState


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


def echo_node(state: AgentState) -> dict[str, object]:
    answer = f"Echo: {state['user_query']}"
    return {
        "draft_answer": answer,
        "final_answer": answer,
        "audit_log": append_audit_entry(state, node="echo", notes="Phase 1 echo stub."),
    }


def build_graph() -> object:
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("echo", echo_node)
    graph_builder.set_entry_point("echo")
    graph_builder.add_edge("echo", END)
    return graph_builder.compile()


@lru_cache(maxsize=1)
def _compiled_graph() -> object:
    return build_graph()


def run_graph(query: str) -> AgentState:
    return _compiled_graph().invoke(make_initial_state(query))
