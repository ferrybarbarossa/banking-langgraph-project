from src.graph import run_graph


def test_phase_1_graph_echoes_query() -> None:
    result = run_graph("What were Apple's biggest risks?")

    assert result["final_answer"] == "Echo: What were Apple's biggest risks?"
    assert result["draft_answer"] == "Echo: What were Apple's biggest risks?"
    assert result["audit_log"][0]["node"] == "echo"
    assert result["audit_log"][0]["notes"] == "Phase 1 echo stub."
