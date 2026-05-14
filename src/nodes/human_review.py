from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.types import interrupt

from src.audit import append_audit_entry
from src.state import AgentState


class HumanReviewResume(TypedDict, total=False):
    decision: Literal["approve", "reject"]
    feedback: str


def human_review_node(state: AgentState) -> dict[str, object]:
    triggered_rules = state["compliance_result"]["triggered_rules"] if state["compliance_result"] else None
    resume_value = interrupt(
        {
            "draft_answer": state["draft_answer"],
            "triggered_rules": triggered_rules or [],
            "reviewer_reasoning": state["compliance_result"]["reasoning"] if state["compliance_result"] else "",
        }
    )
    decision, feedback = parse_human_review_resume(resume_value)

    return {
        "human_decision": decision,
        "human_feedback": feedback,
        "audit_log": append_audit_entry(
            state,
            node="human_review",
            notes=f"Human reviewer selected {decision}.",
            compliance_rules_triggered=triggered_rules,
            human_decision=decision,
        ),
    }


def parse_human_review_resume(resume_value: Any) -> tuple[Literal["approve", "reject"], str | None]:
    if isinstance(resume_value, str):
        decision = resume_value.lower().strip()
        if decision in {"approve", "reject"}:
            return decision, None

    if isinstance(resume_value, dict):
        decision = str(resume_value.get("decision", "")).lower().strip()
        if decision in {"approve", "reject"}:
            feedback = resume_value.get("feedback")
            return decision, str(feedback) if feedback is not None else None

    raise ValueError("Human review resume value must approve or reject the draft.")
