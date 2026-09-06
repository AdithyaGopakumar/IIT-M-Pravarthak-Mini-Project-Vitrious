"""Failure Path Tests

Additional tests for failure handling: agent timeouts, missing records,
and bounded revision limits.
"""

from submission.graph import build_graph
from submission.state.state import make_initial_state
from submission.contracts.agent_outputs import ReviewResult


def test_f1_agent_exception(fresh_db, mock_agents):
    """F1: Agent throws an unexpected exception."""
    mock_agents["investigation"].side_effect = Exception("API Timeout")
    
    graph = build_graph()
    state = make_initial_state("AC-003", "DEL-01")
    
    # LangGraph propagates exceptions; in production we'd wrap invocations
    # but for this test we just ensure it fails loudly.
    try:
        graph.invoke(state)
        assert False, "Should have raised exception"
    except Exception as e:
        assert str(e) == "API Timeout"


def test_f2_revision_loop_boundary(fresh_db, mock_agents):
    """F2: Review agent requests revision twice; graph blocks on second attempt."""
    # Make ReviewAgent always request revision
    mock_agents["review"].return_value = {
        "review_result": ReviewResult(
            status="NEEDS_REVISION",
            policy_passed=False,
            reasoning="Need a faster vendor.",
        ).model_dump(mode="json"),
        "outcome": "NEEDS_REVISION"
    }
    
    graph = build_graph()
    state = make_initial_state("AC-003", "DEL-01")
    
    final_state = graph.invoke(state)
    
    # Should be BLOCKED after max revisions (1)
    assert final_state["outcome"] == "BLOCKED"
    assert final_state["revision_count"] == 1


def test_f3_budget_missing(fresh_db, mock_agents):
    """F3: Sourcing fails if budget lookup fails."""
    mock_agents["sourcing"].return_value = {
        "outcome": "NEEDS_INFORMATION",
        "error_code": "NOT_FOUND",
        "error_message": "Budget row missing for this month."
    }
    
    graph = build_graph()
    state = make_initial_state("AC-003", "DEL-01")
    
    final_state = graph.invoke(state)
    
    assert final_state["outcome"] == "NEEDS_INFORMATION"
    assert final_state["error_code"] == "NOT_FOUND"
