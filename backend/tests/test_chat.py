import json

import pytest
from fastapi.testclient import TestClient

from app import chat as chat_module
from app.main import app


def test_chat_rejects_empty_question() -> None:
    response = TestClient(app).post("/chat", json={"question": "   "})
    assert response.status_code == 400


@pytest.mark.anyio
async def test_chat_events_emit_status_tokens_and_done(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_stream(question: str, passages: list[dict]):
        yield "hello"
        yield " world"

    def fake_retrieve(state: dict) -> dict:
        return {"retrieved_passages": [{"text": "grounded", "source_file": "a.pdf", "page": 1}]}

    def fake_grade(state: dict) -> dict:
        passage = {**state["retrieved_passages"][0], "relevant": True, "score": 1.0}
        return {"graded_passages": [passage]}

    monkeypatch.setattr(chat_module, "retrieve_node", fake_retrieve)
    monkeypatch.setattr(chat_module, "grade_node", fake_grade)
    monkeypatch.setattr(chat_module, "stream_answer", fake_stream)
    events = [event async for event in chat_module.chat_events("question", "conversation")]

    assert [event.splitlines()[0] for event in events] == [
        "event: status",
        "event: status",
        "event: status",
        "event: token",
        "event: token",
        "event: done",
    ]
    done_payload = json.loads(events[-1].split("data: ", 1)[1])
    assert done_payload["conversation_id"] == "conversation"
    assert done_payload["sources"][0]["source_file"] == "a.pdf"