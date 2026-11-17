from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / "docker" / ".env")


def retrieve_graph(question: str, limit: int | None = None) -> list[dict[str, Any]]:
    configured_limit = limit or int(os.getenv("GRAPH_RETRIEVAL_LIMIT", "10"))
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is required for graph retrieval")
    query = """
    MATCH (subject:Entity)-[relationship:RELATED]->(object:Entity)
    WHERE toLower(subject.name) CONTAINS toLower($question)
       OR toLower(object.name) CONTAINS toLower($question)
       OR toLower(relationship.relation) CONTAINS toLower($question)
    RETURN subject.name AS subject, relationship.relation AS relation,
           object.name AS object, relationship.confidence AS score,
           relationship.source_doc AS source_file,
           relationship.source_page AS page
    ORDER BY score DESC
    LIMIT $limit
    """
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        records = driver.execute_query(query, question=question, limit=configured_limit).records
    return [
        {
            "text": f"{record['subject']} {record['relation']} {record['object']}",
            "subject": record["subject"],
            "relation": record["relation"],
            "object": record["object"],
            "score": float(record["score"] or 0.0),
            "source_file": record["source_file"],
            "page": record["page"],
            "source_type": "graph",
        }
        for record in records
    ]


def retrieve_graph_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"retrieved_passages": retrieve_graph(state["question"])}
