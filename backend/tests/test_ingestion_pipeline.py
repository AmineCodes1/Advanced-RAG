from pathlib import Path

from ingestion.chunker import TextChunk
from ingestion.parser import ParsedPage
from ingestion.pipeline import IngestionPipeline
import ingestion.pipeline as pipeline_module


class FakeParser:
    def parse(self, filepath):
        return [ParsedPage("Alice works for Acme.", page=2)]


class FakeChunker:
    def chunk(self, pages, source_file):
        return [TextChunk("Alice works for Acme.", Path(source_file).name, 2, None, 0)]


class FakeEmbedder:
    def embed(self, texts):
        return iter([[0.1, 0.2] for _ in texts])


class FakeStore:
    def upsert(self, chunks, vectors):
        return len(chunks)


def test_pipeline_imports_graph_triplets_when_enabled(monkeypatch, tmp_path) -> None:
    extracted = []

    def fake_extract(text, source_doc, source_page):
        extracted.append((text, source_doc, source_page))
        return []

    monkeypatch.setenv("NEO4J_PASSWORD", "test-password")
    monkeypatch.setattr(pipeline_module, "extract_triplets", fake_extract)
    monkeypatch.setattr(
        pipeline_module,
        "import_triplets",
        lambda *args, **kwargs: {"relationships_seen": 0},
    )

    result = IngestionPipeline(
        parser=FakeParser(),
        chunker=FakeChunker(),
        embedder=FakeEmbedder(),
        store=FakeStore(),
        graph_enabled=True,
    ).ingest_document(tmp_path / "document.pdf")

    assert result.vectors_inserted == 1
    assert result.graph_triplets_extracted == 0
    assert extracted == [("Alice works for Acme.", "document.pdf", 2)]

