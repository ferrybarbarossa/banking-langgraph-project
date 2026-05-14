import pytest

from src.nodes.human_review import parse_human_review_resume


def test_parse_human_review_resume_accepts_string_decision() -> None:
    assert parse_human_review_resume("approve") == ("approve", None)


def test_parse_human_review_resume_accepts_feedback_payload() -> None:
    assert parse_human_review_resume({"decision": "reject", "feedback": "Needs tighter citations."}) == (
        "reject",
        "Needs tighter citations.",
    )


def test_parse_human_review_resume_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="approve or reject"):
        parse_human_review_resume({"decision": "maybe"})
