from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ingestion.chunker import TextChunk, TokenChunker
from ingestion.embedder import Embedder
from ingestion.parser import PdfParser
from ingestion.store import QdrantStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    source_file: str
    chunks_created: int
    vectors_inserted: int
    embedding_seconds: float
    total_seconds: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class IngestionPipeline:
    def __init__(
        self,
        parser: PdfParser | None = None,
        chunker: TokenChunker | None = None,
        embedder: Embedder | None = None,
        store: QdrantStore | None = None,
    ) -> None:
        self.parser = parser or PdfParser()
        self.chunker = chunker or TokenChunker()
        self.embedder = embedder or Embedder()
        self.store = store or QdrantStore(Path(__file__).resolve().parents[1] / "data" / "qdrant")

    def ingest_document(self, filepath: str | Path) -> IngestionResult:
        started = time.perf_counter()
        path = Path(filepath)
        logger.info("Parsing document: %s", path)
        pages = self.parser.parse(path)
        logger.info("Parsed %d document section(s)", len(pages))

        chunks: list[TextChunk] = self.chunker.chunk(pages, path)
        logger.info("Created %d chunks", len(chunks))
        if not chunks:
            return IngestionResult(path.name, 0, 0, 0.0, time.perf_counter() - started)

        embedding_started = time.perf_counter()
        vectors = [list(vector) for vector in self.embedder.embed(chunk.text for chunk in chunks)]
        embedding_seconds = time.perf_counter() - embedding_started
        logger.info("Embedded %d chunks in %.2fs", len(vectors), embedding_seconds)

        inserted = self.store.upsert(chunks, vectors)
        logger.info("Inserted %d vectors into Qdrant", inserted)
        return IngestionResult(
            source_file=path.name,
            chunks_created=len(chunks),
            vectors_inserted=inserted,
            embedding_seconds=embedding_seconds,
            total_seconds=time.perf_counter() - started,
        )


def ingest_document(filepath: str | Path) -> IngestionResult:
    return IngestionPipeline().ingest_document(filepath)
