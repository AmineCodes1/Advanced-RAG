from __future__ import annotations

import json
import os
from typing import Any

import ollama

from graph_import.import_triplets import Triplet

GRAPH_EXTRACTION_MODEL = os.getenv("GRAPH_EXTRACTION_MODEL", "gemma3:4b")


def _parse_response(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    value = json.loads(text)
    if value == {}:
        return []
    if isinstance(value, dict):
        if isinstance(value.get("triplets"), list):
            return value["triplets"]
        return [value]
    if not isinstance(value, list):
        raise ValueError("graph extractor response must be a JSON list or object")
    return value


def extract_triplets(
    text: str,
    source_doc: str,
    source_page: int | None,
    client: ollama.Client | None = None,
) -> list[Triplet]:
    prompt = (
        "Extract the strongest factual entity relationship from the passage. Return "
        "ONLY one JSON object with subject, relation, object, confidence. Use "
        "concise names, preserve the passage meaning, and return {} when there is "
        "no explicit relationship. Confidence must be a number from 0 to 1.\n\n"
        f"Passage:\n{text}"
    )
    response = (client or ollama.Client()).generate(
        model=GRAPH_EXTRACTION_MODEL,
        prompt=prompt,
        format="json",
        options={"temperature": 0},
        keep_alive=0,
    )
    raw = response.get("response", "") if isinstance(response, dict) else response.response
    records = _parse_response(raw)
    triplets: list[Triplet] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"graph extractor item {index} must be an object")
        required = {"subject", "relation", "object", "confidence"}
        if not required.issubset(record):
            raise ValueError(f"graph extractor item {index} is missing required fields")
        confidence = float(record["confidence"])
        if not 0 <= confidence <= 1:
            raise ValueError(f"graph extractor item {index} confidence must be between 0 and 1")
        subject = str(record["subject"]).strip()
        relation = str(record["relation"]).strip()
        object_name = str(record["object"]).strip()
        if not subject or not relation or not object_name:
            raise ValueError(f"graph extractor item {index} contains an empty value")
        triplets.append(
            Triplet(subject, relation, object_name, confidence, source_doc, source_page)
        )
    return triplets
