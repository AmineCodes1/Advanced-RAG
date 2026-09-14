from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    retrieved_passages: list[dict[str, Any]]
    graded_passages: list[dict[str, Any]]
    answer: str
    metadata: dict[str, Any]
