from agent.graph import _should_rewrite, agent_graph
from agent.nodes.grade import _parse_grade
from agent.nodes.hallucination_check import _parse_check, prepare_regeneration_node
from agent.nodes.router import _parse_route
from agent.nodes.rewrite import rewrite_node


def test_graph_contains_mvp_nodes() -> None:
    assert {"retrieve_vector", "grade", "rewrite", "generate"}.issubset(agent_graph.nodes)


def test_grade_parser_accepts_expected_contract() -> None:
    result = _parse_grade('{"relevant": true, "score": 0.8, "reasoning": "supported"}')
    assert result == {"relevant": True, "score": 0.8, "reasoning": "supported"}


def test_grade_parser_accepts_string_booleans_and_scores() -> None:
    result = _parse_grade('{"relevant": "true", "score": "0.8", "reasoning": "supported"}')
    assert result == {"relevant": True, "score": 0.8, "reasoning": "supported"}


def test_grade_parser_rejects_invalid_score() -> None:
    try:
        _parse_grade('{"relevant": true, "score": 2, "reasoning": "bad"}')
    except ValueError as exc:
        assert "score" in str(exc)
    else:
        raise AssertionError("invalid score should be rejected")


def test_rewrite_guard_stops_after_two_iterations(monkeypatch) -> None:
    def fake_generate(*args, **kwargs):
        return {"response": "rewrite the question"}

    monkeypatch.setattr("agent.nodes.rewrite.ollama.Client.generate", fake_generate)

    state = {
        "question": "why is this bad?",
        "graded_passages": [{"score": 0.2, "relevant": False, "reasoning": "weak match"}],
        "rewrite_count": 1,
    }
    assert _should_rewrite(state) == "rewrite"

    rewritten = rewrite_node(state)
    assert rewritten["rewrite_count"] == 2
    assert rewritten["quality_warning"] is True

    guarded_state = {**state, **rewritten}
    assert _should_rewrite(guarded_state) == "generate"


def test_hallucination_guard_allows_one_regeneration() -> None:
    assert _parse_check(
        '{"supported": "false", "unsupported_claims": ["claim"]}'
    ) == {"supported": False, "unsupported_claims": ["claim"]}

    first = prepare_regeneration_node(
        {"unsupported_claims": ["claim"], "regenerate_count": 0, "metadata": {}}
    )
    assert first["regenerate_count"] == 1
    assert "claim" in first["regeneration_instruction"]


def test_router_parser_accepts_valid_route() -> None:
    assert _parse_route('{"route": "hybrid", "confidence": "0.9"}') == {
        "route": "hybrid",
        "confidence": 0.9,
    }


def test_graph_contains_multi_source_nodes() -> None:
    assert {"router", "retrieve_vector", "retrieve_graph", "retrieve_hybrid"}.issubset(agent_graph.nodes)