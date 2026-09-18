from __future__ import annotations

import json
import logging
import os
from typing import Any

import ollama

logger = logging.getLogger(__name__)
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gemma3:4b")


def _parse_grade(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("grader response is not an object")

    relevant = value.get("relevant")
    if isinstance(relevant, str):
        normalized = relevant.strip().lower()
        if normalized in {"true", "false"}:
            relevant = normalized == "true"
    if isinstance(relevant, int) and relevant in {0, 1}:
        relevant = bool(relevant)
    if not isinstance(relevant, bool):
        raise ValueError("relevant must be boolean")

    score = value.get("score")
    if isinstance(score, str):
        score = float(score.strip())
    if not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
        raise ValueError("score must be between 0 and 1")

    reasoning = value.get("reasoning")
    if not isinstance(reasoning, str):
        reasoning = str(reasoning)
    return {"relevant": relevant, "score": float(score), "reasoning": reasoning}


def grade_passage(client: ollama.Client, question: str, passage: dict[str, Any], retries: int = 2) -> dict[str, Any]:
    prompt = (
        "Return ONLY JSON with exactly these keys: relevant (boolean), score "
        "(number 0 to 1), reasoning (string). Judge whether the passage supports "
        "the question.\n"
        f"Question: {question}\nPassage: {passage.get('text', '')}"
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.generate(
                model=JUDGE_MODEL,
                prompt=prompt,
                format="json",
                options={"temperature": 0},
                keep_alive=0,
            )
            raw = response.get("response", "") if isinstance(response, dict) else response.response
            return _parse_grade(raw)
        except (ValueError, TypeError, ollama.ResponseError) as exc:
            last_error = exc
            logger.warning("Grade JSON parsing failed (attempt %d/%d): %s", attempt + 1, retries + 1, exc)
    raise ValueError(f"grader failed after {retries + 1} attempts") from last_error


def grade_node(state: dict[str, Any]) -> dict[str, Any]:
    client = ollama.Client()
    graded: list[dict[str, Any]] = []
    failures = 0
    for passage in state.get("retrieved_passages", []):
        try:
            grade = grade_passage(client, state["question"], passage)
        except ValueError:
            failures += 1
            grade = {
                "relevant": True,
                "score": float(passage.get("score", 0.0)),
                "reasoning": "Grading failed; retained the retrieved passage.",
            }
        graded.append({**passage, **grade})
    metadata = dict(state.get("metadata", {}))
    metadata["grading_failures"] = failures
    metadata["grading_count"] = len(graded)
    return {"graded_passages": graded, "metadata": metadata}
