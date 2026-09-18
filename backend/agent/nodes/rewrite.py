from __future__ import annotations

import os
from typing import Any

import ollama

REWRITE_MODEL = os.getenv("REWRITE_MODEL", "qwen2.5:3b-instruct-q4_K_M")


def rewrite_question(question: str, graded_passages: list[dict[str, Any]]) -> str:
    reasons = [
        passage.get("reasoning", "")
        for passage in graded_passages
        if not passage.get("relevant", False)
    ]
    reason_block = "\n".join(f"- {reason}" for reason in reasons[:3]) or "- The retrieved passages do not clearly answer the question."
    prompt = (
        "Rewrite the user's question to improve retrieval quality. Keep the intent and "
        "topic, but make the query more specific and grounded in the evidence that was weakly matched.\n\n"
        "User question: {question}\n\n"
        "Why the previous attempt underperformed:\n{reasons}\n\n"
        "Return only the rewritten question."
    ).format(question=question, reasons=reason_block)

    client = ollama.Client()
    response = client.generate(
        model=REWRITE_MODEL,
        prompt=prompt,
        options={"temperature": 0.2},
        keep_alive=0,
    )
    text = response.get("response", "") if isinstance(response, dict) else getattr(response, "response", "")
    rewritten = text.strip().strip('"')
    return rewritten or question


def rewrite_node(state: dict[str, Any]) -> dict[str, Any]:
    question = str(state.get("question", "")).strip()
    graded_passages = state.get("graded_passages", []) or []
    rewrite_count = int(state.get("rewrite_count", 0)) + 1
    rewritten = rewrite_question(question, graded_passages)
    quality_warning = rewrite_count >= 2
    return {
        "question": rewritten,
        "rewrite_count": rewrite_count,
        "quality_warning": quality_warning,
        "metadata": {**state.get("metadata", {}), "rewrite_count": rewrite_count, "rewritten_question": rewritten},
    }
