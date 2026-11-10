from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    retrieved_passages: list[dict[str, Any]]
    graded_passages: list[dict[str, Any]]
    answer: str
    rewrite_count: int
    quality_warning: bool
    regenerate_count: int
    regeneration_instruction: str
    hallucination_supported: bool
    hallucination_warning: bool
    unsupported_claims: list[str]
    route: str
    route_confidence: float
    history: list[dict[str, str]]
    metadata: dict[str, Any]
