from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from ingestion.chunker import TextChunk

COLLECTION_NAME = "document_chunks"


class QdrantStore:
    """Persistent local Qdrant store.

    Qdrant supports dense and sparse named vectors, but this first ingestion
    slice only creates the dense index. BM25 sparse retrieval will be added
    with the retrieval phase once its scoring and fusion contract is defined.
    """

    def __init__(self, path: str | Path = "data/qdrant", collection_name: str = COLLECTION_NAME) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.client = QdrantClient(path=str(self.path))

    def ensure_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert(self, chunks: list[TextChunk], vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("Each chunk must have exactly one embedding")
        if not chunks:
            return 0

        self.ensure_collection(len(vectors[0]))
        points = [
            models.PointStruct(
                id=self._point_id(chunk),
                vector=vector,
                payload={
                    "text": chunk.text,
                    "source_file": chunk.source_file,
                    "page": chunk.page,
                    "section": chunk.section,
                    "chunk_index": chunk.chunk_index,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(points)

    def search(self, vector: list[float], limit: int = 10) -> list[dict[str, Any]]:
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
            with_payload=True,
        ).points
        return [
            {
                "id": result.id,
                "score": result.score,
                **(result.payload or {}),
            }
            for result in results
        ]

    @staticmethod
    def _point_id(chunk: TextChunk) -> str:
        identity = f"{chunk.source_file}:{chunk.page}:{chunk.chunk_index}:{chunk.text}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return str(uuid.UUID(hex=digest[:32]))
