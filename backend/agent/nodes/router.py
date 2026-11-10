from __future__ import annotations

import json
import os
from typing import Any

import ollama

ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gemma3:4b")
VALID_ROUTES = {"vector", "graph", "hybrid"}


def _parse_route(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    value = json.loads(text)
    if not isinstance(value, dict) or value.get("route") not in VALID_ROUTES:
        raise ValueError("route must be vector, graph, or hybrid")
    confidence = value.get("confidence")
    if isinstance(confidence, str):
        confidence = float(confidence.strip())
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return {"route": value["route"], "confidence": float(confidence)}


def route_question(
    question: str,
    history: list[dict[str, str]] | None = None,
    client: ollama.Client | None = None,
) -> dict[str, Any]:
    prompt = (
        "Return ONLY JSON with exactly route (vector, graph, or hybrid) and "
        "confidence (number 0 to 1). Choose graph for entity/relationship questions, "
        "vector for factual passage lookup, and hybrid when both are useful.\n"
        f"Question: {question}\nConversation history: {history or []}"
    )
    response = (client or ollama.Client()).generate(
        model=ROUTER_MODEL,
        prompt=prompt,
        format="json",
        options={"temperature": 0},
        keep_alive=0,
    )
    raw = response.get("response", "") if isinstance(response, dict) else response.response
    return _parse_route(raw)


def router_node(state: dict[str, Any]) -> dict[str, Any]:
    result = route_question(state["question"], state.get("history"))
    metadata = dict(state.get("metadata", {}))
    metadata["route"] = result["route"]
    metadata["route_confidence"] = result["confidence"]
    return {"route": result["route"], "route_confidence": result["confidence"], "metadata": metadata}
