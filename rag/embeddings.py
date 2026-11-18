from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_query(self, text: str) -> list[float]:
        ...


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class FakeEmbeddings:
    """Deterministic hashed bag-of-words embeddings for offline RAG."""

    def __init__(self, dimensions: int = 384) -> None:
        if dimensions < 1:
            raise ValueError("Embedding dimensions must be positive")
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = _TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts)

    async def embed_query(self, text: str) -> list[float]:
        return self.embed_text(text)

    # Compatibility aliases for callers that use provider-style naming.
    def embed(self, text: str) -> list[float]:
        return self.embed_text(text)

    def embed_sync(self, text: str) -> list[float]:
        return self.embed_text(text)


def create_embeddings(
    *,
    provider: str = "fake",
    model: str = "fake-hash",
    dimensions: int = 384,
) -> EmbeddingProvider:
    del model
    if provider.lower() != "fake":
        raise ValueError(f"Unsupported embedding provider: {provider}")
    return FakeEmbeddings(dimensions=dimensions)
