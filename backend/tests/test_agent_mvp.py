from agent.graph import agent_graph
from agent.nodes.grade import _parse_grade


def test_graph_contains_mvp_nodes() -> None:
    assert {"retrieve", "grade", "generate"}.issubset(agent_graph.nodes)


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