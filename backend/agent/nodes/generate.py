from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import ollama

GENERATION_MODEL = os.getenv("GENERATION_MODEL", "qwen2.5:3b-instruct-q4_K_M")


def _prompt(question: str, passages: list[dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[Source {index}] {passage.get('text', '')}" for index, passage in enumerate(passages, 1)
    )
    return (
        "Answer the question using only the supplied sources. If the sources do "
        "not contain the answer, say that clearly. Cite sources as [Source N].\n\n"
        f"Question: {question}\n\nSources:\n{context}"
    )


def stream_answer(
    question: str,
    passages: list[dict[str, Any]],
    client: ollama.Client | None = None,
) -> Iterator[str]:
    response = (client or ollama.Client()).generate(
        model=GENERATION_MODEL,
        prompt=_prompt(question, passages),
        stream=True,
        options={"temperature": 0.2},
        keep_alive=0,
    )
    for chunk in response:
        text = chunk.get("response", "") if isinstance(chunk, dict) else chunk.response
        if text:
            yield text


def generate_node(state: dict[str, Any]) -> dict[str, Any]:
    passages = [passage for passage in state.get("graded_passages", []) if passage.get("relevant")]
    answer = "".join(stream_answer(state["question"], passages))
    average_score = 0.0
    if passages:
        average_score = sum(float(passage.get("score", 0.0)) for passage in passages) / len(passages)
    quality_warning = bool(state.get("quality_warning")) or (int(state.get("rewrite_count", 0) or 0) >= 2 and average_score < float(os.getenv("RELEVANCE_THRESHOLD", "0.5")))
    metadata = dict(state.get("metadata", {}))
    metadata["quality_warning"] = quality_warning
    return {"answer": answer, "quality_warning": quality_warning, "metadata": metadata}
