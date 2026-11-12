import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import chat as chat_module
from app.main import app


def test_chat_rejects_empty_question() -> None:
    response = TestClient(app).post("/chat", json={"question": "   "})
    assert response.status_code == 400


def test_agent_trace_websocket_is_scoped_to_conversation() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/agent-trace?conversation_id=trace-test") as websocket:
            asyncio.run(chat_module.trace_hub.publish("other-conversation", {"node": "router"}))
            asyncio.run(chat_module.trace_hub.publish("trace-test", {
                "node": "router",
                "status": "active",
                "timestamp": 1.0,
                "duration_ms": None,
            }))
            assert websocket.receive_json()["node"] == "router"


def test_chat_events_emit_status_tokens_and_done(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_stream(question: str, passages: list[dict], instruction: str | None = None):
        yield "hello"
        yield " world"

    def fake_retrieve(state: dict) -> dict:
        return {"retrieved_passages": [{"text": "grounded", "source_file": "a.pdf", "page": 1}]}

    def fake_grade(state: dict) -> dict:
        passage = {**state["retrieved_passages"][0], "relevant": True, "score": 1.0}
        return {"graded_passages": [passage]}

    def fake_hallucination_check(state: dict) -> dict:
        return {
            "hallucination_supported": True,
            "hallucination_warning": False,
            "unsupported_claims": [],
        }

    monkeypatch.setattr(chat_module, "retrieve_node", fake_retrieve)
    monkeypatch.setattr(chat_module, "router_node", lambda state: {"route": "vector", "route_confidence": 1.0})
    monkeypatch.setattr(chat_module, "grade_node", fake_grade)
    monkeypatch.setattr(chat_module, "stream_answer", fake_stream)
    monkeypatch.setattr(chat_module, "hallucination_check_node", fake_hallucination_check)
    events = asyncio.run(_collect_events())

    assert [event.splitlines()[0] for event in events] == [
        "event: status",
        "event: status",
        "event: status",
        "event: status",
        "event: token",
        "event: token",
        "event: status",
        "event: done",
    ]
    done_payload = json.loads(events[-1].split("data: ", 1)[1])
    assert done_payload["conversation_id"] == "conversation"
    assert done_payload["sources"][0]["source_file"] == "a.pdf"
    assert done_payload["hallucination_warning"] is False


def test_chat_done_includes_graph_subgraph_for_graph_passages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat_module, "router_node", lambda state: {"route": "graph"})
    monkeypatch.setattr(chat_module, "retrieve_graph_node", lambda state: {
        "retrieved_passages": [{
            "text": "Alice works_for Acme",
            "subject": "Alice",
            "relation": "works_for",
            "object": "Acme",
            "source_type": "graph",
            "score": 1.0,
        }]
    })
    monkeypatch.setattr(chat_module, "grade_node", lambda state: {
        "graded_passages": [{**state["retrieved_passages"][0], "relevant": True, "score": 1.0}]
    })
    monkeypatch.setattr(chat_module, "stream_answer", lambda *args, **kwargs: iter(["answer"]))
    monkeypatch.setattr(chat_module, "hallucination_check_node", lambda state: {
        "hallucination_supported": True,
        "hallucination_warning": False,
        "unsupported_claims": [],
    })

    events = asyncio.run(_collect_events())
    done_payload = json.loads(events[-1].split("data: ", 1)[1])

    assert done_payload["graph"] == {
        "nodes": [
            {"id": "Alice", "label": "Alice", "type": "Entity"},
            {"id": "Acme", "label": "Acme", "type": "Entity"},
        ],
        "edges": [{"source": "Alice", "target": "Acme", "relation": "works_for"}],
    }


def test_chat_emits_hallucination_warning_after_one_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def fake_stream(question: str, passages: list[dict], instruction: str | None = None):
        nonlocal attempts
        attempts += 1
        yield f"answer-{attempts}"

    def fake_hallucination_check(state: dict) -> dict:
        return {
            "hallucination_supported": False,
            "hallucination_warning": True,
            "unsupported_claims": ["unsupported claim"],
        }

    monkeypatch.setattr(chat_module, "retrieve_node", lambda state: {
        "retrieved_passages": [{"text": "grounded", "relevant": True, "score": 1.0}]
    })
    monkeypatch.setattr(chat_module, "router_node", lambda state: {"route": "vector", "route_confidence": 1.0})
    monkeypatch.setattr(chat_module, "grade_node", lambda state: {
        "graded_passages": [{**state["retrieved_passages"][0], "relevant": True, "score": 1.0}]
    })
    monkeypatch.setattr(chat_module, "stream_answer", fake_stream)
    monkeypatch.setattr(chat_module, "hallucination_check_node", fake_hallucination_check)
    events = asyncio.run(_collect_events())
    done_payload = json.loads(events[-1].split("data: ", 1)[1])

    assert attempts == 2
    assert done_payload["hallucination_warning"] is True
    assert done_payload["unsupported_claims"] == ["unsupported claim"]


async def _collect_events() -> list[str]:
    return [event async for event in chat_module.chat_events("question", "conversation")]