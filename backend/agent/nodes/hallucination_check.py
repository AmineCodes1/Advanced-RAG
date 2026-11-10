from __future__ import annotations

import json
import logging
import os
from typing import Any

import ollama

logger = logging.getLogger(__name__)
CHECKER_MODEL = os.getenv("CHECKER_MODEL", "gemma3:4b")


def _parse_check(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("hallucination response is not an object")

    supported = value.get("supported")
    if isinstance(supported, str) and supported.strip().lower() in {"true", "false"}:
        supported = supported.strip().lower() == "true"
    if isinstance(supported, int) and supported in {0, 1}:
        supported = bool(supported)
    if not isinstance(supported, bool):
        raise ValueError("supported must be boolean")

    claims = value.get("unsupported_claims", [])
    if not isinstance(claims, list) or not all(isinstance(claim, str) for claim in claims):
        raise ValueError("unsupported_claims must be a list of strings")
    return {"supported": supported, "unsupported_claims": claims}


def check_answer(
    client: ollama.Client,
    answer: str,
    passages: list[dict[str, Any]],
    retries: int = 2,
) -> dict[str, Any]:
    context = "\n\n".join(passage.get("text", "") for passage in passages)
    prompt = (
        "Return ONLY JSON with exactly these keys: supported (boolean) and "
        "unsupported_claims (array of strings). Check whether every claim in the "
        "answer is directly supported by the source context.\\n"
        f"Answer:\\n{answer}\\n\\nSource context:\\n{context}"
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.generate(
                model=CHECKER_MODEL,
                prompt=prompt,
                format="json",
                options={"temperature": 0},
                keep_alive=0,
            )
            raw = response.get("response", "") if isinstance(response, dict) else response.response
            return _parse_check(raw)
        except (ValueError, TypeError, json.JSONDecodeError, ollama.ResponseError) as exc:
            last_error = exc
            logger.warning(
                "Hallucination check failed (attempt %d/%d): %s",
                attempt + 1,
                retries + 1,
                exc,
            )
    raise ValueError(f"hallucination check failed after {retries + 1} attempts") from last_error


def hallucination_check_node(state: dict[str, Any]) -> dict[str, Any]:
    passages = [passage for passage in state.get("graded_passages", []) if passage.get("relevant")]
    result = check_answer(ollama.Client(), state.get("answer", ""), passages)
    metadata = dict(state.get("metadata", {}))
    metadata.update(result)
    return {
        "hallucination_supported": result["supported"],
        "unsupported_claims": result["unsupported_claims"],
        "hallucination_warning": not result["supported"],
        "metadata": metadata,
    }


def prepare_regeneration_node(state: dict[str, Any]) -> dict[str, Any]:
    regenerate_count = int(state.get("regenerate_count", 0)) + 1
    metadata = dict(state.get("metadata", {}))
    metadata["regenerate_count"] = regenerate_count
    return {
        "regenerate_count": regenerate_count,
        "regeneration_instruction": (
            "Only use claims directly supported by the supplied sources. "
            f"Do not make these unsupported claims: {state.get('unsupported_claims', [])}"
        ),
        "metadata": metadata,
    }
