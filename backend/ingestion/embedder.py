from __future__ import annotations

from collections.abc import Iterable, Iterator

from fastembed import TextEmbedding


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", batch_size: int = 32) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
        self.model = TextEmbedding(model_name=model_name)

    def embed(self, texts: Iterable[str]) -> Iterator[list[float]]:
        yield from self.model.embed(list(texts), batch_size=self.batch_size)
