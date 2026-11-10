from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastembed import TextEmbedding

from ingestion.store import QdrantStore


class VectorRetriever:
    def __init__(self, store: QdrantStore | None = None, embedder: TextEmbedding | None = None) -> None:
        self.store = store or QdrantStore(Path(__file__).resolve().parents[2] / "data" / "qdrant")
        self.embedder = embedder or TextEmbedding(model_name=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))

    def retrieve(self, question: str, limit: int = 50) -> list[dict[str, Any]]:
        query_vector = next(iter(self.embedder.embed([question])))
        return self.store.search(list(query_vector), limit=limit)


def retrieve_vector_node(state: dict[str, Any]) -> dict[str, Any]:
    limit = int(os.getenv("RETRIEVAL_LIMIT", "1"))
    passages = VectorRetriever().retrieve(state["question"], limit=limit)
    return {"retrieved_passages": passages}


retrieve_node = retrieve_vector_node
