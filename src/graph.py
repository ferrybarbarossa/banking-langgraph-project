from functools import lru_cache

from langgraph.graph import END, StateGraph

from src.nodes.planner import planner_node
from src.nodes.retrieval import retrieval_agent_node
from src.nodes.semantic_retrieval import semantic_retrieval_node
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


def build_graph() -> object:
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("retrieval_agent", retrieval_agent_node)
    graph_builder.add_node("semantic_retrieval", semantic_retrieval_node)
    graph_builder.set_entry_point("planner")
    graph_builder.add_edge("planner", "retrieval_agent")
    graph_builder.add_edge("retrieval_agent", "semantic_retrieval")
    graph_builder.add_edge("semantic_retrieval", END)
    return graph_builder.compile()


@lru_cache(maxsize=1)
def _compiled_graph() -> object:
    return build_graph()


def run_graph(query: str) -> AgentState:
    return _compiled_graph().invoke(make_initial_state(query))
