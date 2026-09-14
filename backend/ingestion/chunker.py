from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tiktoken

from ingestion.parser import ParsedPage


@dataclass(frozen=True)
class TextChunk:
    text: str
    source_file: str
    page: int | None
    section: str | None
    chunk_index: int


class TokenChunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be >= 0 and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk(self, pages: list[ParsedPage], source_file: str | Path) -> list[TextChunk]:
        source_name = Path(source_file).name
        chunks: list[TextChunk] = []
        chunk_index = 0
        step = self.chunk_size - self.overlap

        for parsed_page in pages:
            tokens = self.tokenizer.encode(parsed_page.text)
            for start in range(0, len(tokens), step):
                token_slice = tokens[start : start + self.chunk_size]
                if not token_slice:
                    continue
                chunks.append(
                    TextChunk(
                        text=self.tokenizer.decode(token_slice),
                        source_file=source_name,
                        page=parsed_page.page,
                        section=parsed_page.section,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1
                if start + self.chunk_size >= len(tokens):
                    break
        return chunks


def chunk_pages(
    pages: list[ParsedPage],
    source_file: str | Path,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[TextChunk]:
    return TokenChunker(chunk_size=chunk_size, overlap=overlap).chunk(pages, source_file)
