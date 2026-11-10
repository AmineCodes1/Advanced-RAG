from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

TRIPLET_KEYS = {"subject", "relation", "object", "confidence", "source_doc", "source_page"}


@dataclass(frozen=True)
class Triplet:
    subject: str
    relation: str
    object: str
    confidence: float
    source_doc: str
    source_page: int | None


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def load_triplets(path: Path) -> list[Triplet]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Triplet JSON must contain a list")

    triplets: list[Triplet] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or not TRIPLET_KEYS.issubset(item):
            raise ValueError(f"Triplet {index} is missing required fields")
        subject = str(item["subject"]).strip()
        relation = str(item["relation"]).strip()
        obj = str(item["object"]).strip()
        source_doc = str(item["source_doc"]).strip()
        confidence = float(item["confidence"])
        source_page = item["source_page"]
        if not subject or not relation or not obj or not source_doc:
            raise ValueError(f"Triplet {index} contains an empty required value")
        if not 0 <= confidence <= 1:
            raise ValueError(f"Triplet {index} confidence must be between 0 and 1")
        if source_page is not None and (isinstance(source_page, bool) or not isinstance(source_page, int)):
            raise ValueError(f"Triplet {index} source_page must be an integer or null")
        triplets.append(Triplet(subject, relation, obj, confidence, source_doc, source_page))
    return triplets


UPSERT_QUERY = """
UNWIND $triplets AS triplet
MERGE (subject:Entity {key: triplet.subject_key})
  ON CREATE SET subject.name = triplet.subject
MERGE (object:Entity {key: triplet.object_key})
  ON CREATE SET object.name = triplet.object
MERGE (subject)-[relationship:RELATED {key: triplet.relationship_key}]->(object)
  ON CREATE SET relationship.relation = triplet.relation,
                relationship.confidence = triplet.confidence,
                relationship.source_doc = triplet.source_doc,
                relationship.source_page = triplet.source_page
  ON MATCH SET relationship.confidence = CASE
    WHEN relationship.confidence < triplet.confidence THEN triplet.confidence
    ELSE relationship.confidence
  END
RETURN count(DISTINCT subject) AS subjects, count(DISTINCT object) AS objects,
       count(relationship) AS relationships
"""


def import_triplets(triplets: list[Triplet], uri: str, user: str, password: str) -> dict[str, int]:
    rows: list[dict[str, Any]] = []
    for triplet in triplets:
        rows.append(
            {
                "subject": triplet.subject,
                "subject_key": normalize_name(triplet.subject),
                "object": triplet.object,
                "object_key": normalize_name(triplet.object),
                "relation": triplet.relation,
                "relationship_key": "|".join(
                    (normalize_name(triplet.subject), normalize_name(triplet.relation), normalize_name(triplet.object))
                ),
                "confidence": triplet.confidence,
                "source_doc": triplet.source_doc,
                "source_page": triplet.source_page,
            }
        )

    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        record = driver.execute_query(UPSERT_QUERY, triplets=rows).records[0]
    return {
        "triplets_read": len(triplets),
        "subjects_seen": record["subjects"],
        "objects_seen": record["objects"],
        "relationships_seen": record["relationships"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import extracted triplets into Neo4j")
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    args = parser.parse_args()
    if not args.password:
        parser.error("Set NEO4J_PASSWORD or pass the Neo4j password through the environment")
    summary = import_triplets(load_triplets(args.json_path), args.uri, args.user, args.password)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
