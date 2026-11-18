from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from rag.embeddings import EmbeddingProvider, FakeEmbeddings


@dataclass(frozen=True)
class VectorDocument:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    vector: list[float] | None = None


@dataclass(frozen=True)
class VectorSearchResult:
    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStoreService(Protocol):
    async def add_documents(
        self,
        documents: list[VectorDocument],
    ) -> int:
        ...

    async def search(
        self,
        query: str | list[float],
        *,
        top_k: int = 5,
        filters: Mapping[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        ...

    async def delete(self, ids: list[str]) -> int:
        ...

    async def clear(self) -> int:
        ...

    async def count(self) -> int:
        ...

    async def health(self) -> bool:
        ...


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(a * a for a in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _matches_filters(
    metadata: Mapping[str, Any],
    filters: Mapping[str, Any] | None,
) -> bool:
    if not filters:
        return True
    return all(metadata.get(key) == value for key, value in filters.items())


class InMemoryVectorStore:
    def __init__(
        self,
        embeddings: EmbeddingProvider | None = None,
        *,
        dimensions: int | None = None,
    ) -> None:
        self.embeddings = embeddings or FakeEmbeddings(
            dimensions or 384
        )
        self._documents: dict[str, tuple[VectorDocument, list[float]]] = {}

    async def add_documents(
        self,
        documents: list[VectorDocument],
    ) -> int:
        missing_vectors = [
            document for document in documents
            if document.vector is None
        ]
        vectors = await self.embeddings.embed_documents(
            [document.text for document in missing_vectors]
        )
        vector_by_index = iter(vectors)
        added = 0

        for document in documents:
            vector = document.vector
            if vector is None:
                vector = next(vector_by_index)
            self._documents[document.id] = (document, vector)
            added += 1
        return added

    async def search(
        self,
        query: str | list[float],
        *,
        top_k: int = 5,
        filters: Mapping[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        if top_k < 1:
            return []
        if isinstance(query, str):
            query_vector = await self.embeddings.embed_query(query)
        else:
            query_vector = query

        ranked: list[VectorSearchResult] = []
        for document_id, (document, document_vector) in self._documents.items():
            if not _matches_filters(document.metadata, filters):
                continue
            ranked.append(
                VectorSearchResult(
                    id=document_id,
                    text=document.text,
                    score=_cosine(query_vector, document_vector),
                    metadata=dict(document.metadata),
                )
            )
        ranked.sort(key=lambda result: (-result.score, result.id))
        return ranked[:top_k]

    async def delete(self, ids: list[str]) -> int:
        deleted = 0
        for document_id in ids:
            if document_id in self._documents:
                del self._documents[document_id]
                deleted += 1
        return deleted

    async def clear(self) -> int:
        deleted = len(self._documents)
        self._documents.clear()
        return deleted

    async def delete_by_article(self, article_id: str) -> int:
        ids = [
            document_id
            for document_id, (document, _) in self._documents.items()
            if document.metadata.get("article_id") == article_id
        ]
        return await self.delete(ids)

    async def count(self) -> int:
        return len(self._documents)

    async def health(self) -> bool:
        return True


class QdrantVectorStore:
    def __init__(
        self,
        *,
        url: str,
        api_key: str = "",
        collection: str = "clouddesk_knowledge",
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        if not url:
            raise ValueError("Qdrant URL is required")
        self.url = url
        self.api_key = api_key
        self.collection = collection
        self.embeddings = embeddings or FakeEmbeddings()
        self._client: Any = None

    def _client_instance(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient
            except ImportError as exc:
                raise RuntimeError(
                    "Qdrant support requires the qdrant-client package"
                ) from exc
            self._client = AsyncQdrantClient(
                url=self.url,
                api_key=self.api_key or None,
            )
        return self._client

    async def add_documents(
        self,
        documents: list[VectorDocument],
    ) -> int:
        if not documents:
            return 0
        client = self._client_instance()
        from qdrant_client.http import models

        missing_vectors = [
            document for document in documents
            if document.vector is None
        ]
        embedded = await self.embeddings.embed_documents(
            [document.text for document in missing_vectors]
        )
        vector_by_index = iter(embedded)
        points = []
        for document in documents:
            vector = document.vector
            if vector is None:
                vector = next(vector_by_index)
            points.append(
                models.PointStruct(
                    id=document.id,
                    vector=vector,
                    payload={
                        "text": document.text,
                        **document.metadata,
                    },
                )
            )

        try:
            from qdrant_client.models import Distance, VectorParams

            collections = await client.get_collections()
            names = {collection.name for collection in collections.collections}
            if self.collection not in names:
                await client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=len(points[0].vector),
                        distance=Distance.COSINE,
                    ),
                )
        except AttributeError:
            pass

        await client.upsert(
            collection_name=self.collection,
            points=points,
        )
        return len(points)

    async def search(
        self,
        query: str | list[float],
        *,
        top_k: int = 5,
        filters: Mapping[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        if top_k < 1:
            return []
        query_vector = (
            await self.embeddings.embed_query(query)
            if isinstance(query, str)
            else query
        )
        client = self._client_instance()
        from qdrant_client.http import models

        qdrant_filter = None
        if filters:
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                    for key, value in filters.items()
                ]
            )

        points = await client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=top_k,
            with_payload=True,
        )
        results = []
        for point in points:
            payload = dict(point.payload or {})
            text = str(payload.pop("text", ""))
            results.append(
                VectorSearchResult(
                    id=str(point.id),
                    text=text,
                    score=float(point.score),
                    metadata=payload,
                )
            )
        return results

    async def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        client = self._client_instance()
        from qdrant_client.http import models

        await client.delete(
            collection_name=self.collection,
            points_selector=models.PointIdsList(points=ids),
        )
        return len(ids)

    async def clear(self) -> int:
        client = self._client_instance()
        collections = await client.get_collections()
        names = {collection.name for collection in collections.collections}
        if self.collection not in names:
            return 0

        result = await client.count(collection_name=self.collection)
        await client.delete_collection(collection_name=self.collection)
        return int(result.count)

    async def count(self) -> int:
        client = self._client_instance()
        result = await client.count(collection_name=self.collection)
        return int(result.count)

    async def health(self) -> bool:
        try:
            await self._client_instance().get_collections()
            return True
        except (
            ImportError,
            RuntimeError,
            OSError,
            TimeoutError,
            ConnectionError,
            httpx.HTTPError,
        ):
            return False


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


def create_vector_store(
    *,
    vector_store: str = "memory",
    embeddings: EmbeddingProvider | None = None,
    qdrant_url: str = "",
    qdrant_api_key: str = "",
    qdrant_collection: str = "clouddesk_knowledge",
) -> VectorStoreService:
    mode = vector_store.lower()
    if mode == "memory":
        return InMemoryVectorStore(embeddings=embeddings)
    if mode == "qdrant":
        return QdrantVectorStore(
            url=qdrant_url,
            api_key=qdrant_api_key,
            collection=qdrant_collection,
            embeddings=embeddings,
        )
    raise ValueError(f"Unsupported vector store: {vector_store}")
