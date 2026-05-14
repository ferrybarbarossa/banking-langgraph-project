from src.state import AgentState


def output_node(state: AgentState) -> dict[str, object]:
    if state["draft_answer"] is None:
        final_answer = "No answer could be produced from the available filing evidence."
    elif state["compliance_result"] is not None and state["compliance_result"]["verdict"] == "pass":
        final_answer = state["draft_answer"]
    elif state["human_decision"] == "approve":
        final_answer = state["draft_answer"]
    else:
        final_answer = "The draft answer was not approved for release."

    return {"final_answer": final_answer}
